"""Tests for the root-zone water balance."""

from __future__ import annotations

import pytest

from custom_components.garden_irrigation.model.balance import (
    apply_day,
    current_deficit,
    depletion_fraction,
    effective_rain,
    soil_water,
    total_available_water,
)

TAW = 23.25  # 150 mm roots × 155 mm/m (loam)


def _day(prev: float, **kwargs: float) -> float:
    params = {
        "et0_mm": 4.0,
        "kc": 0.95,
        "rain_mm": 0.0,
        "irrigation_mm": 0.0,
        "taw_mm": TAW,
        "rain_factor": 0.8,
        "rain_threshold_mm": 2.0,
        **kwargs,
    }
    return apply_day(prev, **params).deficit_mm


def test_total_and_readily_available_water() -> None:
    assert total_available_water(150, 155) == pytest.approx(23.25)
    water = soil_water(150, 155, 0.4)
    assert water.taw_mm == pytest.approx(23.25)
    assert water.raw_mm == pytest.approx(9.3)


def test_depletion_fraction_without_adjustment() -> None:
    assert depletion_fraction(0.4, 7.0, adjust=False) == 0.4
    assert depletion_fraction(0.4, None, adjust=True) == 0.4


@pytest.mark.parametrize(
    ("etc", "expected"),
    [
        (5.0, 0.40),  # reference demand: unchanged
        (7.0, 0.32),  # hot day: less water can be used
        (2.0, 0.52),  # cool day: more water can be used
        (20.0, 0.10),  # clamped to the FAO-56 minimum
        (-20.0, 0.80),  # clamped to the FAO-56 maximum
    ],
)
def test_depletion_fraction_adjusted_for_etc(etc: float, expected: float) -> None:
    assert depletion_fraction(0.4, etc, adjust=True) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("rain", "expected"),
    [
        (0.0, 0.0),
        (1.9, 0.0),  # below threshold: lost
        (2.0, 1.6),  # at threshold: factor applies
        (5.0, 4.0),
        (67.0, 13.8),  # capped at prev deficit (10) + ETc (3.8)
    ],
)
def test_effective_rain(rain: float, expected: float) -> None:
    eff = effective_rain(
        rain, factor=0.8, threshold_mm=2.0, prev_deficit_mm=10.0, etc_mm=3.8
    )
    assert eff == pytest.approx(expected)


def test_dry_day_increases_deficit_by_etc() -> None:
    result = apply_day(
        5.0,
        et0_mm=4.0,
        kc=0.95,
        rain_mm=0.0,
        irrigation_mm=0.0,
        taw_mm=TAW,
        rain_factor=0.8,
        rain_threshold_mm=2.0,
    )
    assert result.etc_mm == pytest.approx(3.8)
    assert result.effective_rain_mm == 0.0
    assert result.irrigation_mm == 0.0
    assert result.deficit_mm == pytest.approx(8.8)


def test_heavy_rain_brings_soil_to_field_capacity() -> None:
    # 26/11/2026: 67 mm of rain on a partly dry lawn.
    assert _day(12.0, et0_mm=0.5, rain_mm=67.0) == 0.0


def test_irrigation_reduces_deficit() -> None:
    assert _day(12.0, irrigation_mm=10.0) == pytest.approx(5.8)


def test_deficit_never_negative_nor_above_taw() -> None:
    assert _day(1.0, irrigation_mm=30.0) == 0.0
    assert _day(22.0, et0_mm=8.0) == TAW


def test_consecutive_dry_days_from_field_capacity() -> None:
    # Spec §8 example: 3 days at ETc ≈ 4 mm -> deficit ≈ 12 mm.
    deficit = 0.0
    for _ in range(3):
        deficit = _day(deficit, et0_mm=4.0, kc=1.0)
    assert deficit == pytest.approx(12.0)


def test_current_deficit() -> None:
    assert current_deficit(10.0, 0.0) == 10.0
    assert current_deficit(10.0, 3.75) == pytest.approx(6.25)
    assert current_deficit(10.0, 15.0) == 0.0
