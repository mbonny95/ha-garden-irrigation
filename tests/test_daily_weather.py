"""Tests for the daily weather reader (recorder hourly statistics)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pytest
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import (
    StatisticsRow,
    async_import_statistics,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.garden_irrigation.daily_weather import (
    MIN_HOURS,
    aggregate_day,
    async_read_day,
)

from .common import HUMIDITY, PRESSURE, RAIN, SOLAR, TEMPERATURE, WIND

DAY = date(2026, 7, 6)

SOURCES = {
    "temperature_entity": TEMPERATURE,
    "humidity_entity": HUMIDITY,
    "solar_radiation_entity": SOLAR,
    "wind_speed_entity": WIND,
    "rain_entity": RAIN,
}


def _mean_rows(count: int, mean: float, low: float, high: float) -> list[StatisticsRow]:
    return [
        {"start": float(h), "end": float(h + 1), "mean": mean, "min": low, "max": high}
        for h in range(count)
    ]


def _rain_rows(changes: list[float]) -> list[StatisticsRow]:
    return [
        {"start": float(h), "end": float(h + 1), "change": c}
        for h, c in enumerate(changes)
    ]


def _full_day() -> dict[str, list[StatisticsRow]]:
    temperature = _mean_rows(24, 17.0, 16.0, 18.0)
    temperature[5]["min"] = 12.3
    temperature[14]["max"] = 21.5
    humidity = _mean_rows(24, 72.0, 70.0, 75.0)
    humidity[4]["max"] = 84.0
    humidity[15]["min"] = 63.0
    return {
        TEMPERATURE: temperature,
        HUMIDITY: humidity,
        SOLAR: _mean_rows(24, 255.44, 0.0, 800.0),
        WIND: _mean_rows(24, 2.0, 0.0, 6.0),
        RAIN: _rain_rows([0.0] * 20 + [1.5, 2.0, 0.5, 0.0]),
    }


def test_complete_day() -> None:
    result = aggregate_day(DAY, SOURCES, _full_day())

    assert result.is_complete
    assert result.incomplete == ()
    assert result.weather.tmax_c == 21.5
    assert result.weather.tmin_c == 12.3
    assert result.weather.rh_max_pct == 84.0
    assert result.weather.rh_min_pct == 63.0
    assert result.weather.rh_mean_pct == pytest.approx(72.0)
    # 255.44 W/m² averaged over the day = 22.07 MJ/m²/day (FAO-56 Example 18).
    assert result.weather.solar_mj_m2 == pytest.approx(22.07, abs=0.01)
    assert result.weather.wind_ms == 2.0
    assert result.weather.pressure_kpa is None
    assert result.rain_mm == pytest.approx(4.0)
    assert result.hours["temperature_entity"] == 24


def test_short_source_is_missing_and_flags_the_day() -> None:
    rows = _full_day()
    rows[SOLAR] = rows[SOLAR][: MIN_HOURS - 1]

    result = aggregate_day(DAY, SOURCES, rows)

    assert not result.is_complete
    assert result.incomplete == ("solar_radiation_entity",)
    assert result.weather.solar_mj_m2 is None
    assert result.hours["solar_radiation_entity"] == MIN_HOURS - 1


def test_minimum_hours_are_enough() -> None:
    rows = _full_day()
    rows[WIND] = rows[WIND][:MIN_HOURS]

    result = aggregate_day(DAY, SOURCES, rows)

    assert result.is_complete
    assert result.weather.wind_ms == 2.0


def test_partial_rain_uses_available_hours() -> None:
    rows = _full_day()
    rows[RAIN] = _rain_rows([3.0, 2.0])

    result = aggregate_day(DAY, SOURCES, rows)

    assert result.incomplete == ("rain_entity",)
    assert result.rain_mm == pytest.approx(5.0)


def test_source_without_statistics() -> None:
    rows = _full_day()
    del rows[RAIN]

    result = aggregate_day(DAY, SOURCES, rows)

    assert result.incomplete == ("rain_entity",)
    assert result.rain_mm == 0.0
    assert result.hours["rain_entity"] == 0


def test_negative_rain_change_is_ignored() -> None:
    rows = _full_day()
    rows[RAIN] = _rain_rows([0.0] * 23 + [-0.2])

    assert aggregate_day(DAY, SOURCES, rows).rain_mm == 0.0


def test_optional_pressure() -> None:
    sources = {**SOURCES, "pressure_entity": PRESSURE}
    rows = _full_day()

    # Missing pressure never makes the day incomplete.
    assert aggregate_day(DAY, sources, rows).is_complete

    rows[PRESSURE] = _mean_rows(24, 100.1, 99.8, 100.4)
    result = aggregate_day(DAY, sources, rows)
    assert result.weather.pressure_kpa == pytest.approx(100.1)


def test_rows_without_values_are_skipped() -> None:
    rows = _full_day()
    for row in rows[WIND]:
        row["mean"] = None

    assert aggregate_day(DAY, SOURCES, rows).weather.wind_ms is None


# --- Against the real recorder ------------------------------------------------------


def _import(
    hass: HomeAssistant,
    entity_id: str,
    unit: str,
    unit_class: str | None,
    rows: list[dict[str, Any]],
    *,
    has_sum: bool = False,
) -> None:
    async_import_statistics(
        hass,
        {
            "mean_type": (
                StatisticMeanType.NONE if has_sum else StatisticMeanType.ARITHMETIC
            ),
            "has_sum": has_sum,
            "name": None,
            "source": "recorder",
            "statistic_id": entity_id,
            "unit_class": unit_class,
            "unit_of_measurement": unit,
        },
        rows,
    )


def _hours(start: datetime, count: int) -> list[datetime]:
    return [start + timedelta(hours=h) for h in range(count)]


async def test_read_day_from_recorder_converts_units(hass: HomeAssistant) -> None:
    await hass.config.async_set_time_zone("Europe/Rome")
    day_start = dt_util.start_of_local_day(DAY)

    # °F and km/h on purpose: the recorder converts them for FAO-56.
    _import(
        hass,
        TEMPERATURE,
        "°F",
        "temperature",
        [
            {"start": h, "mean": 62.6, "min": 54.14, "max": 70.7}
            for h in _hours(day_start, 24)
        ],
    )
    _import(
        hass,
        HUMIDITY,
        "%",
        None,
        [{"start": h, "mean": 72, "min": 63, "max": 84} for h in _hours(day_start, 24)],
    )
    _import(
        hass,
        SOLAR,
        "W/m²",
        None,
        [
            {"start": h, "mean": 255.44, "min": 0, "max": 800}
            for h in _hours(day_start, 24)
        ],
    )
    _import(
        hass,
        WIND,
        "km/h",
        "speed",
        [{"start": h, "mean": 7.2, "min": 0, "max": 20} for h in _hours(day_start, 24)],
    )
    # A cumulative rain counter: 1 mm/h for the last 3 hours of the day,
    # starting one hour before the day so the first change is defined.
    rain_sums = [0.0] * 22 + [1.0, 2.0, 3.0]
    _import(
        hass,
        RAIN,
        "mm",
        "distance",
        [
            {"start": h, "state": s, "sum": s}
            for h, s in zip(
                _hours(day_start - timedelta(hours=1), 25), rain_sums, strict=True
            )
        ],
        has_sum=True,
    )
    await async_wait_recording_done(hass)

    result = await async_read_day(hass, SOURCES, DAY)

    assert result.is_complete
    assert result.hours["temperature_entity"] == 24
    assert result.weather.tmax_c == pytest.approx(21.5, abs=0.01)
    assert result.weather.tmin_c == pytest.approx(12.3, abs=0.01)
    assert result.weather.wind_ms == pytest.approx(2.0)
    assert result.weather.solar_mj_m2 == pytest.approx(22.07, abs=0.01)
    assert result.rain_mm == pytest.approx(3.0)


async def test_read_day_without_statistics(hass: HomeAssistant) -> None:
    result = await async_read_day(hass, SOURCES, DAY)

    assert set(result.incomplete) == set(SOURCES)
    assert result.weather.tmax_c is None
    assert result.rain_mm == 0.0
