"""Scheduler for garden_irrigation.

Two daily local-time triggers - `DEFAULT_EVENING_CHECK_TIME` (20:00) and
`DEFAULT_MORNING_CHECK_TIME` (05:30) - that each simply request a coordinator
refresh. Both the once-per-day finalization of "yesterday" (balance.py,
idempotent via `last_balance_date`) and the always-recomputed, never-persisted
"today so far" preview (recommendation.py) already happen on EVERY
coordinator refresh, regardless of what triggered it - so this module does
not need to special-case which trigger fired to decide what to compute.

A periodic (`MONITOR_INTERVAL`) tick checks WH51/weather staleness and
surfaces it as a Repair issue (see repairs.py). A periodic timer is used here
deliberately and narrowly: staleness is "nothing happened for N hours", which
by definition cannot be noticed by a purely event-driven listener (no new
state means no new event to react to). This is a clock heartbeat, not
recorder polling - every check reads only the current live state
(`hass.states.get`), never touching the recorder. `ir.async_create_issue`/
`async_delete_issue` are themselves idempotent (repairs.py), so this simply
calls create-or-clear on every tick based on the currently computed level -
no separate transition-tracking is needed to avoid spamming the Repairs UI.

The notification system (Telegram/persistent_notification, morning report,
evening preview, cycle-recorded confirmations, and the notify-only WH51
battery/signal/wind/rain-during-cycle advisories) has been removed entirely.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import (
    async_track_time_change,
    async_track_time_interval,
)

from . import repairs
from .const import (
    CONF_HUMIDITY_ENTITY,
    CONF_PRESSURE_ENTITY,
    CONF_SOLAR_RADIATION_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    CONF_WIND_SPEED_ENTITY,
    CONF_ZONE1_SOIL_MOISTURE_ENTITY,
    CONF_ZONE2_SOIL_MOISTURE_ENTITY,
    DEFAULT_EVENING_CHECK_TIME,
    DEFAULT_MORNING_CHECK_TIME,
    DEFAULT_STALE_WEATHER_ERROR_HOURS,
    DEFAULT_STALE_WEATHER_WARNING_MINUTES,
    DEFAULT_STALE_WH51_ERROR_HOURS,
    DEFAULT_STALE_WH51_WARNING_HOURS,
    ZONE_1,
    ZONES,
)

if TYPE_CHECKING:
    from .coordinator import GardenIrrigationCoordinator

_LOGGER = logging.getLogger(__name__)

MONITOR_INTERVAL = timedelta(minutes=15)


def _parse_hms(value: str) -> tuple[int, int, int]:
    """Parse a "HH:MM:SS" const.py default into (hour, minute, second)."""
    hour_str, minute_str, second_str = value.split(":")
    return int(hour_str), int(minute_str), int(second_str)


def _soil_moisture_entity_id(entry: ConfigEntry, zone_id: str) -> str:
    key = (
        CONF_ZONE1_SOIL_MOISTURE_ENTITY
        if zone_id == ZONE_1
        else CONF_ZONE2_SOIL_MOISTURE_ENTITY
    )
    return str(entry.data[key])


def _entity_age(hass: HomeAssistant, entity_id: str, now: datetime) -> timedelta | None:
    """Age of `entity_id`'s current state, or None if missing/unknown/unavailable."""
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unknown", "unavailable"):
        return None
    return now - state.last_updated


def _stale_level(
    age: timedelta | None, warning_threshold: timedelta, error_threshold: timedelta
) -> str | None:
    """ "error"/"warning"/None from `age` (None age = missing data = "error")."""
    if age is None or age >= error_threshold:
        return "error"
    if age >= warning_threshold:
        return "warning"
    return None


class Scheduler:
    """Owns the daily local-time triggers and the periodic staleness monitor.

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
        """05:30 local: guarantee a refresh finalizing the just-completed day."""
        await self._coordinator.async_request_refresh()

    # -- Periodic staleness monitor -----------------------------------------

    async def _handle_monitor_tick(self, now: datetime) -> None:
        """Check WH51/weather staleness and update the matching Repair issues."""
        await self._check_wh51_stale(now)
        await self._check_weather_stale(now)

    async def _check_wh51_stale(self, now: datetime) -> None:
        entry = self._coordinator.entry
        warning = timedelta(hours=DEFAULT_STALE_WH51_WARNING_HOURS)
        error = timedelta(hours=DEFAULT_STALE_WH51_ERROR_HOURS)
        for zone_id in ZONES:
            entity_id = _soil_moisture_entity_id(entry, zone_id)
            age = _entity_age(self.hass, entity_id, now)
            level = _stale_level(age, warning, error)
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
        if level is None:
            repairs.async_clear_weather_stale_issue(self.hass)
        else:
            repairs.async_create_weather_stale_issue(self.hass, level)
