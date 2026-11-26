"""Sanity tests for the agronomic reference tables."""

from __future__ import annotations

import pytest

from custom_components.garden_irrigation.model.crops import (
    CROP_COOL_SEASON_TURF,
    KC_PROFILES,
    kc_for_month,
)
from custom_components.garden_irrigation.model.soils import DEFAULT_SOIL, SOILS


def test_soils_match_fao56_table_19_ranges() -> None:
    # FAO-56 Table 19: θFC - θWP spans 0.05 (sand) to 0.20 m³/m³.
    for soil in SOILS.values():
        assert 50 <= soil.awc_mm_per_m <= 200
        assert soil.max_block_mm > 0
    assert SOILS["sand"].awc_mm_per_m < SOILS["loam"].awc_mm_per_m
    assert DEFAULT_SOIL in SOILS


def test_cool_season_turf_profile() -> None:
    profile = KC_PROFILES[CROP_COOL_SEASON_TURF]
    assert len(profile) == 12
    # Active growth uses the FAO-56 Table 12 value.
    assert kc_for_month(profile, 7) == 0.95
    assert kc_for_month(profile, 1) == 0.70


@pytest.mark.parametrize("month", [0, 13])
def test_kc_for_month_rejects_invalid_month(month: int) -> None:
    with pytest.raises(ValueError):
        kc_for_month(KC_PROFILES[CROP_COOL_SEASON_TURF], month)


def test_kc_for_month_rejects_short_profile() -> None:
    with pytest.raises(ValueError):
        kc_for_month([0.9] * 11, 1)
