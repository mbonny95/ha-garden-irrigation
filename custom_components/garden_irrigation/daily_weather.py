"""Daily FAO-56 weather from the recorder's long-term hourly statistics.

One bounded query per closed local day. The recorder converts every value to
the units FAO-56 needs, whatever unit the source sensor reports.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import fmean

from homeassistant.components.recorder.statistics import (
    StatisticsRow,
    statistics_during_period,
)
from homeassistant.const import (
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
)

from .const import (
    CONF_HUMIDITY_ENTITY,
    CONF_PRESSURE_ENTITY,
    CONF_RAIN_ENTITY,
    CONF_SOLAR_RADIATION_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    CONF_WIND_SPEED_ENTITY,
)
from .model.fao56 import DailyWeather

# A source with fewer hourly rows than this makes the day incomplete.
MIN_HOURS = 20
W_M2_TO_MJ_M2_DAY = 0.0864  # 86400 s / 1e6

SOURCE_FIELDS: tuple[str, ...] = (
    CONF_TEMPERATURE_ENTITY,
    CONF_HUMIDITY_ENTITY,
    CONF_SOLAR_RADIATION_ENTITY,
    CONF_WIND_SPEED_ENTITY,
    CONF_RAIN_ENTITY,
    CONF_PRESSURE_ENTITY,
)
REQUIRED_FIELDS: frozenset[str] = frozenset(SOURCE_FIELDS) - {CONF_PRESSURE_ENTITY}

STATISTICS_UNITS: dict[str, str] = {
    TemperatureConverter.UNIT_CLASS: UnitOfTemperature.CELSIUS,
    SpeedConverter.UNIT_CLASS: UnitOfSpeed.METERS_PER_SECOND,
    PressureConverter.UNIT_CLASS: UnitOfPressure.KPA,
    DistanceConverter.UNIT_CLASS: UnitOfLength.MILLIMETERS,
}


@dataclass(frozen=True, slots=True)
class DayWeather:
    """Weather of one closed local day, with its data coverage."""

    day: date
    weather: DailyWeather
    rain_mm: float  # from the available hours (0.0 without any)
    hours: dict[str, int]  # source field -> hourly rows found
    incomplete: tuple[str, ...]  # required fields below MIN_HOURS

    @property
    def is_complete(self) -> bool:
        """True when every required source covers the day."""
        return not self.incomplete


def aggregate_day(
    day: date,
    sources: Mapping[str, str],
    rows_by_entity: Mapping[str, Sequence[StatisticsRow]],
) -> DayWeather:
    """Turn hourly statistics rows into one FAO-56 day.

    `sources` maps configured source fields to entity ids. Inputs with fewer
    than MIN_HOURS rows are treated as missing, so FAO-56 reports them
    instead of computing ET0 from a partial day. Rain uses whatever hours
    exist.
    """
    rows = {
        field: list(rows_by_entity.get(entity_id, ()))
        for field, entity_id in sources.items()
    }
    hours = {field: len(field_rows) for field, field_rows in rows.items()}

    def usable(field: str) -> list[StatisticsRow]:
        field_rows = rows.get(field, [])
        return field_rows if len(field_rows) >= MIN_HOURS else []

    temperature = usable(CONF_TEMPERATURE_ENTITY)
    humidity = usable(CONF_HUMIDITY_ENTITY)
    solar = _values(usable(CONF_SOLAR_RADIATION_ENTITY), "mean")
    wind = _values(usable(CONF_WIND_SPEED_ENTITY), "mean")
    pressure = _values(usable(CONF_PRESSURE_ENTITY), "mean")

    weather = DailyWeather(
        tmax_c=_max(temperature, "max"),
        tmin_c=_min(temperature, "min"),
        rh_max_pct=_max(humidity, "max"),
        rh_min_pct=_min(humidity, "min"),
        rh_mean_pct=fmean(m) if (m := _values(humidity, "mean")) else None,
        solar_mj_m2=fmean(solar) * W_M2_TO_MJ_M2_DAY if solar else None,
        wind_ms=fmean(wind) if wind else None,
        pressure_kpa=fmean(pressure) if pressure else None,
    )
    rain = sum(_values(rows.get(CONF_RAIN_ENTITY, []), "change"))
    incomplete = tuple(
        field
        for field in SOURCE_FIELDS
        if field in REQUIRED_FIELDS and hours.get(field, 0) < MIN_HOURS
    )
    return DayWeather(
        day=day,
        weather=weather,
        rain_mm=max(rain, 0.0),
        hours=hours,
        incomplete=incomplete,
    )


async def async_read_day(
    hass: HomeAssistant, sources: Mapping[str, str], day: date
) -> DayWeather:
    """Read the hourly statistics of `day` (local time) and aggregate them."""
    start = dt_util.start_of_local_day(day)
    end = dt_util.start_of_local_day(day + timedelta(days=1))
    entity_ids = set(sources.values())
    rows = await get_instance(hass).async_add_executor_job(
        statistics_during_period,
        hass,
        start,
        end,
        entity_ids,
        "hour",
        STATISTICS_UNITS,
        {"mean", "min", "max", "change"},
    )
    return aggregate_day(day, sources, rows)


def _values(rows: Sequence[StatisticsRow], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, int | float):
            values.append(float(value))
    return values


def _max(rows: Sequence[StatisticsRow], key: str) -> float | None:
    values = _values(rows, key)
    return max(values) if values else None


def _min(rows: Sequence[StatisticsRow], key: str) -> float | None:
    values = _values(rows, key)
    return min(values) if values else None
