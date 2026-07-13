"""Scheduler for garden_irrigation.

Milestone 7 added two daily local-time triggers -
`DEFAULT_EVENING_CHECK_TIME` (20:00) and `DEFAULT_MORNING_CHECK_TIME` (05:30)
- that each simply request a coordinator refresh. Both the once-per-day
finalization of "yesterday" (balance.py, idempotent via `last_balance_date`)
and the always-recomputed, never-persisted "today so far" preview
(recommendation.py) already happen on EVERY coordinator refresh, regardless
of what triggered it - so this module does not need to special-case which
trigger fired to decide what to compute.

Milestone 8 adds:
  - the morning report (sent after the 05:30 refresh, from the just-finalized
    `coordinator.data["recommendation"]`);
  - a periodic (`MONITOR_INTERVAL`) advisory tick checking WH51/weather
    staleness, WH51 battery/signal, and strong wind. A periodic timer is used
    here deliberately and narrowly: staleness is "nothing happened for N
    hours", which by definition cannot be noticed by a purely event-driven
    listener (no new state means no new event to react to). This is a clock
    heartbeat, not recorder polling - every check reads only the current live
    state (`hass.states.get`) or already-computed weather.py aggregates,
    never touching the recorder.
  - transition-based deduplication: each check tracks its own last-known
    severity and only notifies/creates-or-clears a repair issue when that
    severity actually changes, never on every tick while unchanged.

Milestone 9 adds one more check to the same periodic tick: a rain-rate
advisory while a manual cycle is declared active (`coordinator.cycle_zone`,
set/cleared by button.py's start/end cycle buttons - M7/M8 could not add
this yet since that state did not exist). It follows the exact same
notify-only, transition-deduplicated pattern as the wind/battery/signal
checks above (no repair issue - this is a transient advisory, not a
configuration problem) and reuses `CONF_RAIN_RATE_ENTITY`, already read
elsewhere for the same "is it raining right now" diagnostic purpose
(CLAUDE.md). Its message text is a small local IT/EN lookup rather than an
addition to notify.py's `translate()` table - notify.py is out of scope to
touch in M9.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import (
    async_track_time_change,
    async_track_time_interval,
)

from . import repairs
from .const import (
    CONF_HUMIDITY_ENTITY,
    CONF_PRESSURE_ENTITY,
    CONF_RAIN_RATE_ENTITY,
    CONF_SOLAR_RADIATION_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    CONF_WIND_SPEED_ENTITY,
    CONF_ZONE1_BATTERY_ENTITY,
    CONF_ZONE1_SIGNAL_ENTITY,
    CONF_ZONE1_SOIL_MOISTURE_ENTITY,
    CONF_ZONE2_BATTERY_ENTITY,
    CONF_ZONE2_SIGNAL_ENTITY,
    CONF_ZONE2_SOIL_MOISTURE_ENTITY,
    DEFAULT_EVENING_CHECK_TIME,
    DEFAULT_MORNING_CHECK_TIME,
    DEFAULT_STALE_WEATHER_ERROR_HOURS,
    DEFAULT_STALE_WEATHER_WARNING_MINUTES,
    DEFAULT_STALE_WH51_ERROR_HOURS,
    DEFAULT_STALE_WH51_WARNING_HOURS,
    DEFAULT_WH51_BATTERY_WARNING_PERCENT,
    DEFAULT_WH51_SIGNAL_WARNING,
    DEFAULT_WIND_WARNING_AVG_KMH,
    DEFAULT_WIND_WARNING_GUST_KMH,
    ZONE_1,
    ZONES,
)
from .notify import translate

if TYPE_CHECKING:
    from .coordinator import GardenIrrigationCoordinator

_LOGGER = logging.getLogger(__name__)

MONITOR_INTERVAL = timedelta(minutes=15)


def _parse_hms(value: str) -> tuple[int, int, int]:
    """Parse a "HH:MM:SS" const.py default into (hour, minute, second)."""
    hour_str, minute_str, second_str = value.split(":")
    return int(hour_str), int(minute_str), int(second_str)


def _soil_moisture_entity_id(entry: Any, zone_id: str) -> str:
    key = (
        CONF_ZONE1_SOIL_MOISTURE_ENTITY
        if zone_id == ZONE_1
        else CONF_ZONE2_SOIL_MOISTURE_ENTITY
    )
    return str(entry.data[key])


def _battery_entity_id(entry: Any, zone_id: str) -> str | None:
    key = CONF_ZONE1_BATTERY_ENTITY if zone_id == ZONE_1 else CONF_ZONE2_BATTERY_ENTITY
    value = entry.data.get(key)
    return str(value) if value else None


def _signal_entity_id(entry: Any, zone_id: str) -> str | None:
    key = CONF_ZONE1_SIGNAL_ENTITY if zone_id == ZONE_1 else CONF_ZONE2_SIGNAL_ENTITY
    value = entry.data.get(key)
    return str(value) if value else None


def _entity_age(hass: HomeAssistant, entity_id: str, now: datetime) -> timedelta | None:
    """Age of `entity_id`'s current state, or None if missing/unknown/unavailable."""
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unknown", "unavailable"):
        return None
    return now - state.last_updated


def _numeric_state(hass: HomeAssistant, entity_id: str) -> float | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unknown", "unavailable"):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _stale_level(
    age: timedelta | None, warning_threshold: timedelta, error_threshold: timedelta
) -> str | None:
    """ "error"/"warning"/None from `age` (None age = missing data = "error")."""
    if age is None or age >= error_threshold:
        return "error"
    if age >= warning_threshold:
        return "warning"
    return None


def _rain_during_cycle_message(
    hass: HomeAssistant, zone_id: str, rain_rate: float
) -> str:
    """Small local IT/EN lookup - notify.py's shared table is out of scope
    to touch in M9 (see module docstring)."""
    if hass.config.language == "it":
        return (
            f"Sta piovendo (intensità {rain_rate:.1f} mm/h) durante un ciclo "
            f"dichiarato attivo per {zone_id}: valuta di interrompere l'irrigazione."
        )
    return (
        f"It's raining (rate {rain_rate:.1f} mm/h) during a declared active "
        f"cycle for {zone_id}: consider stopping irrigation."
    )


class Scheduler:
    """Owns the daily local-time triggers and the periodic advisory monitor.

    Not an entity: plain domain logic held by the coordinator
    (`coordinator.scheduler`).
    """

    def __init__(
        self, hass: HomeAssistant, coordinator: GardenIrrigationCoordinator
    ) -> None:
        """Build the scheduler; no triggers are registered until async_setup."""
        self.hass = hass
        self._coordinator = coordinator
        self._unsub_preview: CALLBACK_TYPE | None = None
        self._unsub_finalize: CALLBACK_TYPE | None = None
        self._unsub_monitor: CALLBACK_TYPE | None = None
        self._monitor_severity: dict[str, str | None] = {}

    async def async_setup(self) -> None:
        """Register the 20:00/05:30 triggers and the periodic monitor tick."""
        preview_hour, preview_minute, preview_second = _parse_hms(
            DEFAULT_EVENING_CHECK_TIME
        )
        finalize_hour, finalize_minute, finalize_second = _parse_hms(
            DEFAULT_MORNING_CHECK_TIME
        )
        self._unsub_preview = async_track_time_change(
            self.hass,
            self._handle_evening_preview,
            hour=preview_hour,
            minute=preview_minute,
            second=preview_second,
        )
        self._unsub_finalize = async_track_time_change(
            self.hass,
            self._handle_morning_finalize,
            hour=finalize_hour,
            minute=finalize_minute,
            second=finalize_second,
        )
        self._unsub_monitor = async_track_time_interval(
            self.hass, self._handle_monitor_tick, MONITOR_INTERVAL
        )

    async def async_shutdown(self) -> None:
        """Unsubscribe every trigger."""
        if self._unsub_preview is not None:
            self._unsub_preview()
            self._unsub_preview = None
        if self._unsub_finalize is not None:
            self._unsub_finalize()
            self._unsub_finalize = None
        if self._unsub_monitor is not None:
            self._unsub_monitor()
            self._unsub_monitor = None

    async def _handle_evening_preview(self, now: datetime) -> None:
        """20:00 local: guarantee a refresh so the preview reflects today so far."""
        await self._coordinator.async_request_refresh()

    async def _handle_morning_finalize(self, now: datetime) -> None:
        """05:30 local: guarantee a refresh, then send the morning report."""
        await self._coordinator.async_request_refresh()
        await self._send_morning_report()

    async def _send_morning_report(self) -> None:
        data = self._coordinator.data
        if not data:
            return
        recommendations = data.get("recommendation", {})
        lines: list[str] = []
        for zone_id in ZONES:
            bundle = recommendations.get(zone_id)
            if bundle is None:
                continue
            final = bundle.final
            if not final.ready:
                lines.append(
                    translate(self.hass, "morning_report_not_ready", zone_id=zone_id)
                )
            elif final.needs_irrigation:
                lines.append(
                    translate(
                        self.hass,
                        "morning_report_needs",
                        zone_id=zone_id,
                        mm=final.recommended_mm or 0.0,
                    )
                )
            else:
                lines.append(translate(self.hass, "morning_report_ok", zone_id=zone_id))
        if not lines:
            return
        await self._coordinator.notifier.async_send(
            "\n".join(lines),
            title=translate(self.hass, "morning_report_title"),
            notification_id="morning_report",
        )

    # -- Periodic advisory monitor -----------------------------------------

    async def _handle_monitor_tick(self, now: datetime) -> None:
        """Check WH51/weather staleness, WH51 battery/signal, wind, and
        rain-rate during a declared active cycle."""
        await self._check_wh51_stale(now)
        await self._check_weather_stale(now)
        await self._check_wh51_battery_signal()
        await self._check_wind()
        await self._check_rain_during_cycle()

    async def _apply_transition(
        self, key: str, level: str | None, message: str | None
    ) -> bool:
        """Update `key`'s tracked severity; return True if it just changed.

        Notifying only happens when `level` differs from the last tick's
        value for this `key` - the actual dedup mechanism for every check.
        """
        previous = self._monitor_severity.get(key)
        if level == previous:
            return False
        self._monitor_severity[key] = level
        if level is not None and message is not None:
            await self._coordinator.notifier.async_send(
                message, title="Garden Irrigation", notification_id=key
            )
        return True

    async def _check_wh51_stale(self, now: datetime) -> None:
        entry = self._coordinator.entry
        warning = timedelta(hours=DEFAULT_STALE_WH51_WARNING_HOURS)
        error = timedelta(hours=DEFAULT_STALE_WH51_ERROR_HOURS)
        for zone_id in ZONES:
            entity_id = _soil_moisture_entity_id(entry, zone_id)
            age = _entity_age(self.hass, entity_id, now)
            level = _stale_level(age, warning, error)
            message = (
                translate(self.hass, "wh51_stale", zone_id=zone_id, level=level)
                if level is not None
                else None
            )
            changed = await self._apply_transition(
                f"wh51_stale_{zone_id}", level, message
            )
            if not changed:
                continue
            if level is None:
                repairs.async_clear_wh51_stale_issue(self.hass, zone_id)
            else:
                repairs.async_create_wh51_stale_issue(self.hass, zone_id, level)

    async def _check_weather_stale(self, now: datetime) -> None:
        entry = self._coordinator.entry
        entity_ids = [
            entry.data[CONF_TEMPERATURE_ENTITY],
            entry.data[CONF_HUMIDITY_ENTITY],
            entry.data[CONF_PRESSURE_ENTITY],
            entry.data[CONF_SOLAR_RADIATION_ENTITY],
            entry.data[CONF_WIND_SPEED_ENTITY],
        ]
        ages = [_entity_age(self.hass, entity_id, now) for entity_id in entity_ids]
        # The single most-stale required entity determines overall freshness:
        # ET0 has no automatic fallback, so even one broken input matters.
        oldest = None if any(age is None for age in ages) else max(ages)  # type: ignore[type-var]
        warning = timedelta(minutes=DEFAULT_STALE_WEATHER_WARNING_MINUTES)
        error = timedelta(hours=DEFAULT_STALE_WEATHER_ERROR_HOURS)
        level = _stale_level(oldest, warning, error)
        message = (
            translate(self.hass, "weather_stale", level=level)
            if level is not None
            else None
        )
        changed = await self._apply_transition("weather_stale", level, message)
        if not changed:
            return
        if level is None:
            repairs.async_clear_weather_stale_issue(self.hass)
        else:
            repairs.async_create_weather_stale_issue(self.hass, level)

    async def _check_wh51_battery_signal(self) -> None:
        entry = self._coordinator.entry
        for zone_id in ZONES:
            battery_entity = _battery_entity_id(entry, zone_id)
            if battery_entity is not None:
                percent = _numeric_state(self.hass, battery_entity)
                level = (
                    "warning"
                    if percent is not None
                    and percent < DEFAULT_WH51_BATTERY_WARNING_PERCENT
                    else None
                )
                message = (
                    translate(
                        self.hass, "wh51_battery_low", zone_id=zone_id, percent=percent
                    )
                    if level is not None
                    else None
                )
                await self._apply_transition(f"wh51_battery_{zone_id}", level, message)

            signal_entity = _signal_entity_id(entry, zone_id)
            if signal_entity is not None:
                signal = _numeric_state(self.hass, signal_entity)
                level = (
                    "warning"
                    if signal is not None and signal <= DEFAULT_WH51_SIGNAL_WARNING
                    else None
                )
                message = (
                    translate(self.hass, "wh51_signal_low", zone_id=zone_id)
                    if level is not None
                    else None
                )
                await self._apply_transition(f"wh51_signal_{zone_id}", level, message)

    async def _check_wind(self) -> None:
        snapshot = self._coordinator.weather.today_snapshot()
        avg = snapshot.wind_mean
        gust = snapshot.wind_gust_max
        triggered = (avg is not None and avg >= DEFAULT_WIND_WARNING_AVG_KMH) or (
            gust is not None and gust >= DEFAULT_WIND_WARNING_GUST_KMH
        )
        level = "warning" if triggered else None
        message = (
            translate(self.hass, "wind_strong", avg=avg or 0.0, gust=gust or 0.0)
            if level is not None
            else None
        )
        await self._apply_transition("wind", level, message)

    async def _check_rain_during_cycle(self) -> None:
        """Rain-rate "stop advisory" while a cycle is declared active.

        No repair issue (see module docstring): this is a transient,
        situational advisory, not a configuration problem - the same
        notify-only pattern as wind/battery/signal above.
        """
        zone_id = self._coordinator.cycle_zone
        if zone_id is None:
            # No active cycle: nothing to check, and silently resolve any
            # advisory left over from a cycle that has since ended.
            await self._apply_transition("rain_during_cycle", None, None)
            return

        rain_rate = _numeric_state(
            self.hass, self._coordinator.entry.data[CONF_RAIN_RATE_ENTITY]
        )
        level = "warning" if rain_rate is not None and rain_rate > 0 else None
        message = (
            _rain_during_cycle_message(self.hass, zone_id, rain_rate)
            if level is not None and rain_rate is not None
            else None
        )
        await self._apply_transition("rain_during_cycle", level, message)
