"""Coordinator: daily water balance, catch-up of missed days, user actions.

Once a day, at the configured run time, the previous local day is closed:
its weather is read from the recorder statistics, ET0 is computed and every
zone's deficit is advanced by one day. Days missed while Home Assistant was
off are processed in order. Between runs the data (current deficit and
recommendation) is recomputed from the store, which needs no I/O.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import repairs
from .const import DOMAIN, RETENTION_DAYS
from .daily_weather import DayWeather, async_read_day
from .model.balance import (
    SoilWater,
    apply_day,
    current_deficit,
    depletion_fraction,
    soil_water,
    total_available_water,
)
from .model.crops import kc_for_month
from .model.fao56 import Et0Result, compute_et0
from .model.recommendation import Recommendation, ZoneState, recommend
from .settings import (
    OperatingOptions,
    ZoneConfig,
    site_from_entry,
    weather_sources,
    zones_from_entry,
)
from .store import (
    DayRecord,
    GardenIrrigationStore,
    IrrigationRecord,
    WeatherDayRecord,
)

_LOGGER = logging.getLogger(__name__)

REFRESH_INTERVAL = timedelta(minutes=15)
MAX_IRRIGATION_MINUTES = 240.0
MAX_IRRIGATION_MM = 100.0


@dataclass(frozen=True, slots=True)
class ZoneSnapshot:
    """Everything known about a zone right now."""

    config: ZoneConfig
    soil: SoilWater
    kc_today: float
    closed_deficit_mm: float | None  # at the end of the last closed day
    deficit_mm: float | None  # now, after irrigation recorded since then
    last_balance_date: date | None
    last_day: DayRecord | None
    pending_irrigation_mm: float
    irrigation_7d_mm: float
    last_irrigation: datetime | None
    recommendation: Recommendation


@dataclass(frozen=True, slots=True)
class CoordinatorData:
    """Data shared with the entities."""

    zones: dict[str, ZoneSnapshot]
    weather_day: WeatherDayRecord | None


class GardenIrrigationCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Single source of truth of the integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        store: GardenIrrigationStore,
    ) -> None:
        """Read the configuration once: any change reloads the entry."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=REFRESH_INTERVAL,
        )
        self.entry = entry
        self.store = store
        self.site = site_from_entry(entry)
        self.sources = weather_sources(entry)
        self.options = OperatingOptions.from_entry(entry)
        self.zones = zones_from_entry(entry)
        self._run_lock = asyncio.Lock()

    # --- Scheduling ---------------------------------------------------------

    @callback
    def async_schedule_daily_run(self) -> list[CALLBACK_TYPE]:
        """Run at the configured time every day, and once after startup."""
        run_time = self.options.run_time
        return [
            async_track_time_change(
                self.hass,
                self._async_handle_run_time,
                hour=run_time.hour,
                minute=run_time.minute,
                second=run_time.second,
            ),
            async_at_started(self.hass, self._async_handle_started),
        ]

    async def _async_handle_run_time(self, now: datetime) -> None:
        await self.async_run_daily(now)

    async def _async_handle_started(self, hass: HomeAssistant) -> None:
        await self.async_run_daily()

    def last_closed_day(self, now: datetime) -> date:
        """Most recent day that may be closed at `now`.

        Yesterday counts as closed only from the run time on, so its last
        hourly statistics have certainly been compiled.
        """
        local = dt_util.as_local(now)
        days_back = 1 if local.time() >= self.options.run_time else 2
        return local.date() - timedelta(days=days_back)

    # --- Daily balance -----------------------------------------------------

    async def async_run_daily(self, now: datetime | None = None) -> None:
        """Close every day not processed yet, then refresh the data."""
        async with self._run_lock:
            changed = await self._async_close_days(now or dt_util.now())
        if changed:
            await self.store.async_save()
        await self.async_refresh()

    async def _async_close_days(self, now: datetime) -> bool:
        target = self.last_closed_day(now)
        oldest = target - timedelta(days=RETENTION_DAYS - 1)

        zone_starts: dict[str, date] = {}
        for zone_id in self.zones:
            state = self.store.zone(zone_id)
            if state["deficit_mm"] is None or state["last_balance_date"] is None:
                continue  # waiting for the user to set the starting deficit
            first = date.fromisoformat(state["last_balance_date"]) + timedelta(days=1)
            if first <= target:
                zone_starts[zone_id] = max(first, oldest)

        last_weather = self.store.last_weather_day
        weather_start = (
            max(date.fromisoformat(last_weather["date"]) + timedelta(days=1), oldest)
            if last_weather is not None
            else target
        )
        start = min([weather_start, *zone_starts.values()])
        if start > target:
            return False

        day_weather: DayWeather | None = None
        day = start
        while day <= target:
            day_weather = await async_read_day(self.hass, self.sources, day)
            et0 = compute_et0(
                day_weather.weather,
                self.site,
                day,
                allow_hargreaves=self.options.hargreaves_fallback,
            )
            for zone_id, first in zone_starts.items():
                if first <= day:
                    self._apply_zone_day(zone_id, day, day_weather, et0)
            self.store.last_weather_day = _weather_record(day_weather, et0)
            day += timedelta(days=1)

        if day_weather is not None:
            repairs.async_update_source_issues(self.hass, self.sources, day_weather)
        self.store.prune_history(target)
        return True

    def _apply_zone_day(
        self, zone_id: str, day: date, day_weather: DayWeather, et0: Et0Result
    ) -> None:
        zone = self.zones[zone_id]
        state = self.store.zone(zone_id)
        prev = state["deficit_mm"]
        assert prev is not None  # only zones with a deficit are scheduled
        irrigation = sum(
            record["mm"]
            for record in state["irrigations"]
            if _local_date(record["timestamp"]) == day
        )
        result = apply_day(
            prev,
            et0_mm=et0.et0_mm,
            kc=kc_for_month(zone.kc_monthly, day.month),
            rain_mm=day_weather.rain_mm,
            irrigation_mm=irrigation,
            taw_mm=total_available_water(zone.root_depth_mm, zone.awc_mm_per_m),
            rain_factor=self.options.rain_factor,
            rain_threshold_mm=self.options.rain_threshold_mm,
        )
        state["deficit_mm"] = result.deficit_mm
        state["last_balance_date"] = day.isoformat()
        state["days"].append(
            {
                "date": day.isoformat(),
                "et0_mm": et0.et0_mm,
                "etc_mm": result.etc_mm,
                "rain_mm": day_weather.rain_mm,
                "effective_rain_mm": result.effective_rain_mm,
                "irrigation_mm": irrigation,
                "deficit_mm": result.deficit_mm,
                "et0_estimate": et0.is_estimate,
                "incomplete": list(day_weather.incomplete),
            }
        )

    # --- Data for the entities ------------------------------------------------

    async def _async_update_data(self) -> CoordinatorData:
        now = dt_util.now()
        return CoordinatorData(
            zones={
                zone_id: self._snapshot(zone, now)
                for zone_id, zone in self.zones.items()
            },
            weather_day=self.store.last_weather_day,
        )

    def _snapshot(self, zone: ZoneConfig, now: datetime) -> ZoneSnapshot:
        state = self.store.zone(zone.zone_id)
        closed = state["deficit_mm"]
        last_balance = (
            date.fromisoformat(state["last_balance_date"])
            if state["last_balance_date"]
            else None
        )
        irrigations = [
            (dt_util.as_local(datetime.fromisoformat(r["timestamp"])), r["mm"])
            for r in state["irrigations"]
        ]
        pending = sum(
            mm
            for when, mm in irrigations
            if last_balance is None or when.date() > last_balance
        )
        deficit = current_deficit(closed, pending) if closed is not None else None
        last_day = state["days"][-1] if state["days"] else None
        p = depletion_fraction(
            zone.depletion_fraction,
            last_day["etc_mm"] if last_day else None,
            adjust=self.options.adjust_p_for_etc,
        )
        soil = soil_water(zone.root_depth_mm, zone.awc_mm_per_m, p)
        week_ago = now - timedelta(days=7)
        irrigation_7d = sum(mm for when, mm in irrigations if when > week_ago)
        last_irrigation = max((when for when, _ in irrigations), default=None)

        recommendation = recommend(
            ZoneState(
                deficit_mm=deficit,
                raw_mm=soil.raw_mm,
                area_m2=zone.area_m2,
                source_rates_mm_per_min=zone.source_rates,
                max_block_mm=zone.max_block_mm,
                block_pause_min=self.options.block_pause_min,
                now=now,
                last_irrigation=last_irrigation,
                min_interval_h=self.options.min_interval_h,
                irrigation_7d_mm=irrigation_7d,
                weekly_cap_mm=self.options.weekly_cap_mm,
            )
        )
        return ZoneSnapshot(
            config=zone,
            soil=soil,
            kc_today=kc_for_month(zone.kc_monthly, dt_util.as_local(now).month),
            closed_deficit_mm=closed,
            deficit_mm=deficit,
            last_balance_date=last_balance,
            last_day=last_day,
            pending_irrigation_mm=pending,
            irrigation_7d_mm=irrigation_7d,
            last_irrigation=last_irrigation,
            recommendation=recommendation,
        )

    # --- User actions --------------------------------------------------------

    def _zone(self, zone_id: str) -> ZoneConfig:
        if (zone := self.zones.get(zone_id)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_zone"
            )
        return zone

    async def async_record_irrigation(
        self,
        zone_id: str,
        source: str,
        *,
        minutes: float | None = None,
        mm: float | None = None,
        note: str | None = None,
    ) -> IrrigationRecord:
        """Record an irrigation done now, given its duration or its amount."""
        zone = self._zone(zone_id)
        if (minutes is None) == (mm is None):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="minutes_or_mm"
            )
        rate = zone.source_rates.get(source)
        if minutes is not None:
            if rate is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="source_rate_missing",
                    translation_placeholders={"zone": zone.name, "source": source},
                )
            mm = minutes * rate
        elif mm is not None and rate is not None:
            minutes = mm / rate
        assert mm is not None
        record: IrrigationRecord = {
            "timestamp": dt_util.now().isoformat(),
            "source": source,
            "mm": mm,
            "minutes": minutes,
            "note": note or None,
        }
        self.store.zone(zone_id)["irrigations"].append(record)
        await self.store.async_save()
        await self.async_refresh()
        return record

    async def async_set_deficit(self, zone_id: str, deficit_mm: float) -> None:
        """Set the current deficit of a zone (e.g. 0 after soaking rain)."""
        zone = self._zone(zone_id)
        taw = total_available_water(zone.root_depth_mm, zone.awc_mm_per_m)
        if deficit_mm > taw:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="deficit_above_taw",
                translation_placeholders={"taw": f"{taw:.1f}"},
            )
        today = dt_util.now().date()
        state = self.store.zone(zone_id)
        # The value is the deficit right now: today's irrigation is already
        # in it, and is subtracted again when today is closed.
        irrigation_today = sum(
            record["mm"]
            for record in state["irrigations"]
            if _local_date(record["timestamp"]) == today
        )
        state["deficit_mm"] = min(deficit_mm + irrigation_today, taw)
        state["last_balance_date"] = (today - timedelta(days=1)).isoformat()
        await self.store.async_save()
        await self.async_refresh()


def _local_date(timestamp: str) -> date:
    return dt_util.as_local(datetime.fromisoformat(timestamp)).date()


def _weather_record(day_weather: DayWeather, et0: Et0Result) -> WeatherDayRecord:
    return {
        "date": day_weather.day.isoformat(),
        "et0_mm": et0.et0_mm,
        "et0_method": et0.method.value if et0.method else None,
        "rain_mm": day_weather.rain_mm,
        "incomplete": list(day_weather.incomplete),
        "missing": list(et0.missing),
    }
