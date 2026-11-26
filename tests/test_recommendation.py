"""Tests for the zone recommendation."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.garden_irrigation.model.recommendation import (
    Advisory,
    Reason,
    SoilSensorReading,
    ZoneState,
    recommend,
    split_blocks,
)

NOW = datetime(2026, 7, 15, 5, 30, tzinfo=UTC)

BASE = ZoneState(
    deficit_mm=12.0,
    raw_mm=9.3,
    area_m2=38.0,
    source_rates_mm_per_min={"mains": 0.25, "tank": 0.2},
    max_block_mm=6.0,
    block_pause_min=30,
    now=NOW,
)


def _codes(messages: tuple[object, ...]) -> list[str]:
    return [m.code for m in messages]  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("amount", "max_block", "expected"),
    [
        (0.0, 6.0, ()),
        (5.0, 6.0, (5.0,)),
        (6.0, 6.0, (6.0,)),
        (12.0, 6.0, (6.0, 6.0)),
        (13.0, 6.0, (13 / 3,) * 3),
    ],
)
def test_split_blocks(
    amount: float, max_block: float, expected: tuple[float, ...]
) -> None:
    assert split_blocks(amount, max_block) == pytest.approx(expected)


def test_unknown_deficit() -> None:
    rec = recommend(replace(BASE, deficit_mm=None))

    assert rec.needs_irrigation is None
    assert rec.amount_mm == 0.0
    assert rec.sources == {}
    assert _codes(rec.reasons) == [Reason.DEFICIT_UNKNOWN]


def test_below_raw_no_irrigation() -> None:
    rec = recommend(replace(BASE, deficit_mm=5.0))

    assert rec.needs_irrigation is False
    assert rec.amount_mm == 0.0
    assert rec.liters == 0.0
    assert rec.blocks_mm == ()
    assert rec.sources["mains"].total_minutes == 0.0
    assert _codes(rec.reasons) == [Reason.DEFICIT_BELOW_RAW]
    assert rec.reasons[0].params == {"deficit_mm": 5.0, "raw_mm": 9.3}
    assert rec.warnings == ()


def test_reaching_raw_recommends_refilling_the_deficit() -> None:
    rec = recommend(BASE)

    assert rec.needs_irrigation is True
    assert _codes(rec.reasons) == [Reason.DEFICIT_REACHED_RAW]
    assert rec.amount_mm == 12.0
    assert rec.liters == pytest.approx(456.0)
    assert rec.blocks_mm == (6.0, 6.0)
    assert rec.block_pause_min == 30
    assert rec.sources["mains"].total_minutes == pytest.approx(48.0)
    assert rec.sources["mains"].block_minutes == pytest.approx((24.0, 24.0))
    assert rec.sources["tank"].total_minutes == pytest.approx(60.0)
    assert rec.warnings == ()


def test_deficit_exactly_at_raw_needs_irrigation() -> None:
    assert recommend(replace(BASE, deficit_mm=9.3)).needs_irrigation is True


def test_only_sources_with_a_rate_are_planned() -> None:
    rec = recommend(replace(BASE, source_rates_mm_per_min={"mains": 0.25, "tank": 0}))

    assert list(rec.sources) == ["mains"]


def test_no_source_rate_warning() -> None:
    rec = recommend(replace(BASE, source_rates_mm_per_min={}))

    assert _codes(rec.warnings) == [Advisory.NO_SOURCE_RATE]


def test_min_interval_warning() -> None:
    rec = recommend(
        replace(BASE, last_irrigation=NOW - timedelta(hours=30), min_interval_h=48)
    )

    assert _codes(rec.warnings) == [Advisory.MIN_INTERVAL]
    assert rec.warnings[0].params["hours_since"] == pytest.approx(30.0)
    # A warning never changes the decision or the amount.
    assert rec.needs_irrigation is True
    assert rec.amount_mm == 12.0


def test_min_interval_respected_or_disabled() -> None:
    long_ago = NOW - timedelta(hours=72)
    assert (
        recommend(replace(BASE, last_irrigation=long_ago, min_interval_h=48)).warnings
        == ()
    )
    recent = NOW - timedelta(hours=1)
    assert (
        recommend(replace(BASE, last_irrigation=recent, min_interval_h=0)).warnings
        == ()
    )


def test_weekly_cap_warning() -> None:
    rec = recommend(replace(BASE, irrigation_7d_mm=25.0, weekly_cap_mm=30.0))

    assert _codes(rec.warnings) == [Advisory.WEEKLY_CAP]
    assert rec.amount_mm == 12.0


def test_weekly_cap_not_reached() -> None:
    rec = recommend(replace(BASE, irrigation_7d_mm=10.0, weekly_cap_mm=30.0))

    assert rec.warnings == ()


def test_soil_sensor_wet_contradicts_irrigation() -> None:
    sensor = SoilSensorReading(value_pct=72, dry_pct=40, wet_pct=68)
    rec = recommend(replace(BASE, soil_sensor=sensor))

    assert _codes(rec.warnings) == [Advisory.SOIL_SENSOR_WET]
    assert rec.needs_irrigation is True


def test_soil_sensor_dry_contradicts_no_irrigation() -> None:
    sensor = SoilSensorReading(value_pct=35, dry_pct=40, wet_pct=68)
    rec = recommend(replace(BASE, deficit_mm=3.0, soil_sensor=sensor))

    assert _codes(rec.warnings) == [Advisory.SOIL_SENSOR_DRY]
    assert rec.needs_irrigation is False


def test_soil_sensor_without_thresholds_is_silent() -> None:
    sensor = SoilSensorReading(value_pct=90, dry_pct=None, wet_pct=None)
    assert recommend(replace(BASE, soil_sensor=sensor)).warnings == ()
    assert recommend(replace(BASE, deficit_mm=1.0, soil_sensor=sensor)).warnings == ()


def test_soil_sensor_agreeing_is_silent() -> None:
    sensor = SoilSensorReading(value_pct=50, dry_pct=40, wet_pct=68)
    assert recommend(replace(BASE, soil_sensor=sensor)).warnings == ()


def test_rain_forecast_warning() -> None:
    rec = recommend(replace(BASE, forecast_rain_mm=8.0, forecast_threshold_mm=2.0))

    assert _codes(rec.warnings) == [Advisory.RAIN_FORECAST]
    assert rec.amount_mm == 12.0


def test_small_rain_forecast_is_ignored() -> None:
    rec = recommend(replace(BASE, forecast_rain_mm=1.0, forecast_threshold_mm=2.0))
    assert rec.warnings == ()
    rec = recommend(replace(BASE, forecast_rain_mm=0.0, forecast_threshold_mm=0.0))
    assert rec.warnings == ()


def test_warnings_only_when_irrigation_is_needed() -> None:
    rec = recommend(
        replace(
            BASE,
            deficit_mm=2.0,
            last_irrigation=NOW - timedelta(hours=1),
            min_interval_h=48,
            irrigation_7d_mm=50,
            weekly_cap_mm=30,
            forecast_rain_mm=10,
        )
    )
    assert rec.warnings == ()
