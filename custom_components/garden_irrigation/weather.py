"""Daily weather aggregation for garden_irrigation.

Milestone 2 scope only: local, persistent, time-weighted accumulators fed by
`async_track_state_change_event`. No ET0/balance/recommendation computation
happens here (see et0.py / balance.py / recommendation.py in later
milestones) — this module only produces validated daily weather aggregates
that later milestones will consume.

Recovery strategy on restart, in priority order:
1. Our own periodically persisted accumulator state (Store), if it matches
   today's local date — this is the primary recovery path.
2. A single bounded recorder backfill (today's local midnight -> now) via
   `recorder.get_instance(hass).async_add_executor_job(...)`, only when (1)
   is missing or stale. Never a continuous/looping history query.
3. Live `state_changed` events from that point onward.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.recorder import history
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DAILY_RAINFALL_ENTITY,
    CONF_HUMIDITY_ENTITY,
    CONF_PRESSURE_ENTITY,
    CONF_SOLAR_RADIATION_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    CONF_WIND_GUST_ENTITY,
    CONF_WIND_SPEED_ENTITY,
    DEFAULT_RAIN_RESET_TOLERANCE_MM,
    STORAGE_KEY_STATE,
)
from .storage import GardenIrrigationStore

_LOGGER = logging.getLogger(__name__)

DAILY_HISTORY_MAX_DAYS = 35
SAVE_DELAY_SECONDS = 30

FIELD_TEMPERATURE = "temperature"
FIELD_HUMIDITY = "humidity"
FIELD_PRESSURE = "pressure"
FIELD_SOLAR_RADIATION = "solar_radiation"
FIELD_WIND_SPEED = "wind_speed"
FIELD_WIND_GUST = "wind_gust"
FIELD_RAIN = "rain"

# Fields that use the shared time-weighted accumulator (min/max + weighted
# sum). wind_gust is a bare running max (not a continuous physical quantity
# worth time-weighting) and rain uses its own reset-aware accumulator.
MEAN_FIELDS = (
    FIELD_TEMPERATURE,
    FIELD_HUMIDITY,
    FIELD_PRESSURE,
    FIELD_SOLAR_RADIATION,
    FIELD_WIND_SPEED,
)


def _parse_float(state: State) -> float | None:
    """Return the numeric value of a state, or None if unknown/unavailable/invalid."""
    if state.state in ("unknown", "unavailable"):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class _FinalizedField:
    """A closed-out time-weighted field, ready to become a daily history entry."""

    minimum: float | None
    maximum: float | None
    weighted_sum: float | None
    total_seconds: float | None

    @property
    def mean(self) -> float | None:
        """Time-weighted mean over the closed interval."""
        if self.weighted_sum is None or not self.total_seconds:
            return None
        return self.weighted_sum / self.total_seconds

    @property
    def integral_mj(self) -> float | None:
        """Time integral in MJ/m² (for solar irradiance in W/m²)."""
        if self.weighted_sum is None:
            return None
        return self.weighted_sum / 1_000_000


@dataclass
class _TimeWeightedAccumulator:
    """Running min/max and a time-weighted sum (sum of value * dt_seconds) for one field.

    `add_sample` treats the value in effect at each sample's timestamp as
    constant until the next sample (or until `as_of`/`midnight` for reads),
    which is exactly how a physical sensor's last known reading behaves
    between updates.
    """

    weighted_sum: float = 0.0
    total_seconds: float = 0.0
    minimum: float | None = None
    maximum: float | None = None
    last_value: float | None = None
    last_ts: datetime | None = None

    def add_sample(self, value: float, ts: datetime) -> None:
        """Close the previous interval up to `ts`, then open a new one at `value`."""
        if (
            self.last_ts is not None
            and self.last_value is not None
            and ts > self.last_ts
        ):
            dt_seconds = (ts - self.last_ts).total_seconds()
            self.weighted_sum += self.last_value * dt_seconds
            self.total_seconds += dt_seconds
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)
        self.last_value = value
        self.last_ts = ts

    def _closed_totals(self, as_of: datetime) -> tuple[float, float]:
        weighted_sum = self.weighted_sum
        total_seconds = self.total_seconds
        if (
            self.last_ts is not None
            and self.last_value is not None
            and as_of > self.last_ts
        ):
            dt_seconds = (as_of - self.last_ts).total_seconds()
            weighted_sum += self.last_value * dt_seconds
            total_seconds += dt_seconds
        return weighted_sum, total_seconds

    def mean_as_of(self, as_of: datetime) -> float | None:
        """Time-weighted mean including the still-open interval up to `as_of`."""
        if self.minimum is None:
            return None
        weighted_sum, total_seconds = self._closed_totals(as_of)
        if total_seconds <= 0:
            return self.last_value
        return weighted_sum / total_seconds

    def integral_mj_as_of(self, as_of: datetime) -> float | None:
        """Time integral in MJ/m² including the still-open interval up to `as_of`."""
        if self.minimum is None:
            return None
        weighted_sum, _ = self._closed_totals(as_of)
        return weighted_sum / 1_000_000

    def finalize_and_reset(self, midnight: datetime) -> _FinalizedField:
        """Close the day at `midnight`, then reset, carrying the last known
        value forward as the opening sample of the new day (the physical
        measurement does not reset just because our calendar-day accounting
        does).
        """
        if self.minimum is None:
            finalized = _FinalizedField(None, None, None, None)
        else:
            weighted_sum, total_seconds = self._closed_totals(midnight)
            finalized = _FinalizedField(
                self.minimum, self.maximum, weighted_sum, total_seconds
            )
        self.weighted_sum = 0.0
        self.total_seconds = 0.0
        self.minimum = self.last_value
        self.maximum = self.last_value
        if self.last_ts is not None:
            self.last_ts = midnight
        return finalized

    def to_dict(self) -> dict[str, Any]:
        """Serialize for Store persistence."""
        return {
            "weighted_sum": self.weighted_sum,
            "total_seconds": self.total_seconds,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "last_value": self.last_value,
            "last_ts": self.last_ts.isoformat() if self.last_ts else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> _TimeWeightedAccumulator:
        """Restore from a previously persisted dict (see to_dict)."""
        last_ts_raw = data.get("last_ts")
        last_ts = dt_util.parse_datetime(last_ts_raw) if last_ts_raw else None
        return cls(
            weighted_sum=float(data.get("weighted_sum", 0.0)),
            total_seconds=float(data.get("total_seconds", 0.0)),
            minimum=data.get("minimum"),
            maximum=data.get("maximum"),
            last_value=data.get("last_value"),
            last_ts=last_ts,
        )


@dataclass
class _RainAccumulator:
    """Reset-aware daily rain accumulator.

    Strictly increasing timestamps (out-of-order/duplicate updates ignored);
    a configurable reset tolerance absorbs small sensor decrements as noise
    (delta=0) instead of misreading them as a station reset; a genuine drop
    below the tolerance is treated as a station reset, where the new raw
    value itself becomes the delta. The very first raw value ever seen
    (whether live or from backfill) is recorded as a baseline only — never
    inferred as a delta, since we cannot know what happened before it.
    """

    reset_tolerance_mm: float
    daily_mm: float = 0.0
    last_raw: float | None = None
    last_ts: datetime | None = None

    def add_sample(self, raw: float, ts: datetime) -> None:
        """Process one raw reading, updating daily_mm per the reset rules above."""
        if self.last_ts is not None and ts <= self.last_ts:
            return  # out-of-order or duplicate: ignored, strictly increasing only
        if self.last_raw is None:
            self.last_raw = raw
            self.last_ts = ts
            return
        raw_delta = raw - self.last_raw
        if raw_delta >= 0:
            delta = raw_delta
        elif -raw_delta <= self.reset_tolerance_mm:
            delta = 0.0
        else:
            delta = raw  # station reset detected; raw already IS since-reset rain
        self.daily_mm = max(0.0, self.daily_mm + delta)
        self.last_raw = raw
        self.last_ts = ts

    def finalize_and_reset(self) -> float:
        """Return today's total and reset it; the raw baseline is NOT reset
        (the physical station counter is independent of our calendar-day
        accounting boundary)."""
        finalized = self.daily_mm
        self.daily_mm = 0.0
        return finalized

    def to_dict(self) -> dict[str, Any]:
        """Serialize for Store persistence."""
        return {
            "daily_mm": self.daily_mm,
            "last_raw": self.last_raw,
            "last_ts": self.last_ts.isoformat() if self.last_ts else None,
        }

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], reset_tolerance_mm: float
    ) -> _RainAccumulator:
        """Restore from a previously persisted dict (see to_dict)."""
        last_ts_raw = data.get("last_ts")
        last_ts = dt_util.parse_datetime(last_ts_raw) if last_ts_raw else None
        return cls(
            reset_tolerance_mm=reset_tolerance_mm,
            daily_mm=float(data.get("daily_mm", 0.0)),
            last_raw=data.get("last_raw"),
            last_ts=last_ts,
        )


@dataclass(frozen=True)
class DailyWeatherSnapshot:
    """A read-only view of one calendar day's aggregates (finalized or live-so-far)."""

    day: date
    temp_min: float | None
    temp_max: float | None
    temp_mean: float | None
    rh_min: float | None
    rh_max: float | None
    rh_mean: float | None
    pressure_mean: float | None
    wind_mean: float | None
    wind_gust_max: float | None
    solar_mj: float | None
    rain_mm: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize for the daily_history Store buffer."""
        return {
            "date": self.day.isoformat(),
            "temp_min": self.temp_min,
            "temp_max": self.temp_max,
            "temp_mean": self.temp_mean,
            "rh_min": self.rh_min,
            "rh_max": self.rh_max,
            "rh_mean": self.rh_mean,
            "pressure_mean": self.pressure_mean,
            "wind_mean": self.wind_mean,
            "wind_gust_max": self.wind_gust_max,
            "solar_mj": self.solar_mj,
            "rain_mm": self.rain_mm,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DailyWeatherSnapshot:
        """Restore from a previously persisted dict (see to_dict)."""
        return cls(
            day=date.fromisoformat(data["date"]),
            temp_min=data.get("temp_min"),
            temp_max=data.get("temp_max"),
            temp_mean=data.get("temp_mean"),
            rh_min=data.get("rh_min"),
            rh_max=data.get("rh_max"),
            rh_mean=data.get("rh_mean"),
            pressure_mean=data.get("pressure_mean"),
            wind_mean=data.get("wind_mean"),
            wind_gust_max=data.get("wind_gust_max"),
            solar_mj=data.get("solar_mj"),
            rain_mm=float(data.get("rain_mm", 0.0)),
        )


class WeatherAggregator:
    """Owns the daily weather accumulators for one config entry.

    Not an entity: this is plain domain logic held by the coordinator
    (`coordinator.weather`). Later milestones read `today_snapshot()` /
    `get_finalized_day()` to feed ET0/balance computation; none of that
    computation happens here.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Build the entity map from the config entry; accumulators start empty."""
        self.hass = hass
        self._entry = entry
        self._store = GardenIrrigationStore(hass, STORAGE_KEY_STATE)
        self._other_stored_data: dict[str, Any] = {}

        self._entity_to_field: dict[str, str] = self._build_entity_map(entry.data)

        self._fields: dict[str, _TimeWeightedAccumulator] = {
            name: _TimeWeightedAccumulator() for name in MEAN_FIELDS
        }
        self._wind_gust_max: float | None = None
        self._rain = _RainAccumulator(
            reset_tolerance_mm=DEFAULT_RAIN_RESET_TOLERANCE_MM
        )
        self._current_day: date = dt_util.now().date()
        self._daily_history: list[DailyWeatherSnapshot] = []

        self._unsub_state: CALLBACK_TYPE | None = None
        self._unsub_midnight: CALLBACK_TYPE | None = None

    @staticmethod
    def _build_entity_map(data: Mapping[str, Any]) -> dict[str, str]:
        mapping = {
            data[CONF_TEMPERATURE_ENTITY]: FIELD_TEMPERATURE,
            data[CONF_HUMIDITY_ENTITY]: FIELD_HUMIDITY,
            data[CONF_PRESSURE_ENTITY]: FIELD_PRESSURE,
            data[CONF_SOLAR_RADIATION_ENTITY]: FIELD_SOLAR_RADIATION,
            data[CONF_WIND_SPEED_ENTITY]: FIELD_WIND_SPEED,
            data[CONF_DAILY_RAINFALL_ENTITY]: FIELD_RAIN,
        }
        if wind_gust_entity := data.get(CONF_WIND_GUST_ENTITY):
            mapping[wind_gust_entity] = FIELD_WIND_GUST
        return mapping

    async def async_setup(self) -> None:
        """Restore persisted/backfilled state and start listening for updates."""
        stored = await self._store.async_load()
        self._other_stored_data = {k: v for k, v in stored.items() if k != "weather"}
        weather_data = stored.get("weather")
        today = dt_util.now().date()

        restored_today = False
        if weather_data is not None:
            if weather_data.get("current_day") == today.isoformat():
                self._restore_from_dict(weather_data)
                restored_today = True
            else:
                self._daily_history = [
                    DailyWeatherSnapshot.from_dict(item)
                    for item in weather_data.get("daily_history", [])
                ][-DAILY_HISTORY_MAX_DAYS:]

        self._current_day = today

        if not restored_today:
            await self._async_backfill_today()

        self._unsub_state = async_track_state_change_event(
            self.hass, list(self._entity_to_field), self._handle_state_change
        )
        self._unsub_midnight = async_track_time_change(
            self.hass, self._handle_midnight, hour=0, minute=0, second=0
        )

    async def async_shutdown(self) -> None:
        """Stop listening and force an immediate (non-debounced) persistence flush."""
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        if self._unsub_midnight is not None:
            self._unsub_midnight()
            self._unsub_midnight = None
        await self._async_force_flush()

    def _restore_from_dict(self, weather_data: Mapping[str, Any]) -> None:
        accumulators = weather_data.get("accumulators", {})
        for name in MEAN_FIELDS:
            if name in accumulators:
                self._fields[name] = _TimeWeightedAccumulator.from_dict(
                    accumulators[name]
                )
        self._wind_gust_max = weather_data.get("wind_gust_max")
        if rain_data := weather_data.get("rain"):
            self._rain = _RainAccumulator.from_dict(
                rain_data, DEFAULT_RAIN_RESET_TOLERANCE_MM
            )
        self._daily_history = [
            DailyWeatherSnapshot.from_dict(item)
            for item in weather_data.get("daily_history", [])
        ][-DAILY_HISTORY_MAX_DAYS:]

    async def _async_backfill_today(self) -> None:
        """Bounded, one-shot recorder backfill for today only (never a loop).

        Only runs when persisted state for today is missing/stale. Replays
        history chronologically through the same accumulators used for live
        updates, so the reset/no-double-count rules apply identically.
        """
        if "recorder" not in self.hass.config.components:
            _LOGGER.debug("Recorder not available; skipping weather backfill")
            return

        start = dt_util.start_of_local_day()
        end = dt_util.now()
        entity_ids = list(self._entity_to_field)

        try:
            history_data = await get_instance(self.hass).async_add_executor_job(
                history.get_significant_states,
                self.hass,
                start,
                end,
                entity_ids,
            )
        except Exception:
            _LOGGER.warning(
                "Weather backfill failed; continuing with live data only",
                exc_info=True,
            )
            return

        samples: list[tuple[datetime, str, State]] = []
        for entity_id, states in history_data.items():
            field = self._entity_to_field.get(entity_id)
            if field is None:
                continue
            for state in states:
                if not isinstance(state, State):
                    continue
                samples.append((state.last_updated, field, state))
        samples.sort(key=lambda item: item[0])

        for ts, field, state in samples:
            value = _parse_float(state)
            if value is None:
                continue
            self._apply_sample(field, value, ts)

    @callback
    def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state is None:
            return
        field = self._entity_to_field.get(new_state.entity_id)
        if field is None:
            return
        value = _parse_float(new_state)
        if value is None:
            return
        self._apply_sample(field, value, new_state.last_updated)
        self._schedule_save()

    def _apply_sample(self, field: str, value: float, ts: datetime) -> None:
        if field == FIELD_RAIN:
            self._rain.add_sample(value, ts)
        elif field == FIELD_WIND_GUST:
            self._wind_gust_max = (
                value
                if self._wind_gust_max is None
                else max(self._wind_gust_max, value)
            )
        else:
            self._fields[field].add_sample(value, ts)

    async def _handle_midnight(self, now: datetime) -> None:
        """Finalize the closed day into history, reset accumulators, force-flush."""
        snapshot = self._finalize_current_day(now)
        self._daily_history.append(snapshot)
        self._daily_history = self._daily_history[-DAILY_HISTORY_MAX_DAYS:]
        self._current_day = now.date()
        await self._async_force_flush()

    def _finalize_current_day(self, midnight: datetime) -> DailyWeatherSnapshot:
        temp = self._fields[FIELD_TEMPERATURE].finalize_and_reset(midnight)
        humidity = self._fields[FIELD_HUMIDITY].finalize_and_reset(midnight)
        pressure = self._fields[FIELD_PRESSURE].finalize_and_reset(midnight)
        solar = self._fields[FIELD_SOLAR_RADIATION].finalize_and_reset(midnight)
        wind = self._fields[FIELD_WIND_SPEED].finalize_and_reset(midnight)
        wind_gust_max = self._wind_gust_max
        self._wind_gust_max = None
        rain_mm = self._rain.finalize_and_reset()
        return DailyWeatherSnapshot(
            day=self._current_day,
            temp_min=temp.minimum,
            temp_max=temp.maximum,
            temp_mean=temp.mean,
            rh_min=humidity.minimum,
            rh_max=humidity.maximum,
            rh_mean=humidity.mean,
            pressure_mean=pressure.mean,
            wind_mean=wind.mean,
            wind_gust_max=wind_gust_max,
            solar_mj=solar.integral_mj,
            rain_mm=rain_mm,
        )

    def today_snapshot(self, as_of: datetime | None = None) -> DailyWeatherSnapshot:
        """Non-destructive view of the current (in-progress) day, as of `as_of`."""
        as_of = as_of or dt_util.now()
        temp = self._fields[FIELD_TEMPERATURE]
        humidity = self._fields[FIELD_HUMIDITY]
        pressure = self._fields[FIELD_PRESSURE]
        solar = self._fields[FIELD_SOLAR_RADIATION]
        wind = self._fields[FIELD_WIND_SPEED]
        return DailyWeatherSnapshot(
            day=self._current_day,
            temp_min=temp.minimum,
            temp_max=temp.maximum,
            temp_mean=temp.mean_as_of(as_of),
            rh_min=humidity.minimum,
            rh_max=humidity.maximum,
            rh_mean=humidity.mean_as_of(as_of),
            pressure_mean=pressure.mean_as_of(as_of),
            wind_mean=wind.mean_as_of(as_of),
            wind_gust_max=self._wind_gust_max,
            solar_mj=solar.integral_mj_as_of(as_of),
            rain_mm=self._rain.daily_mm,
        )

    def get_finalized_day(self, target_date: date) -> DailyWeatherSnapshot | None:
        """Return the finalized snapshot for `target_date`, if it's in the buffer."""
        for entry in reversed(self._daily_history):
            if entry.day == target_date:
                return entry
        return None

    def _weather_save_data(self) -> dict[str, Any]:
        return {
            "current_day": self._current_day.isoformat(),
            "accumulators": {name: acc.to_dict() for name, acc in self._fields.items()},
            "wind_gust_max": self._wind_gust_max,
            "rain": self._rain.to_dict(),
            "daily_history": [item.to_dict() for item in self._daily_history],
        }

    def _full_save_data(self) -> dict[str, Any]:
        return {**self._other_stored_data, "weather": self._weather_save_data()}

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._full_save_data, SAVE_DELAY_SECONDS)

    async def _async_force_flush(self) -> None:
        await self._store.async_save(self._full_save_data())
