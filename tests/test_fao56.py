"""FAO-56 ET0 validated against the manual's worked examples."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from custom_components.garden_irrigation.model.fao56 import (
    DailyWeather,
    Et0Method,
    Site,
    actual_vapour_pressure,
    compute_et0,
    extraterrestrial_radiation,
    hargreaves,
    penman_monteith,
    pressure_from_elevation,
    wind_at_2m,
)

# FAO-56 Example 18: Brussels (50°48'N, 100 m), 6 July. Wind measured at 10 m
# (10 km/h). Rs = 22.07 MJ m-2 day-1 is the value the example derives from
# 9.25 h of sunshine; we feed it directly, as a pyranometer would.
BRUSSELS = Site(latitude_deg=50.8, elevation_m=100, anemometer_height_m=10)
BRUSSELS_DAY = date(2026, 7, 6)
BRUSSELS_WEATHER = DailyWeather(
    tmax_c=21.5,
    tmin_c=12.3,
    rh_max_pct=84,
    rh_min_pct=63,
    solar_mj_m2=22.07,
    wind_ms=10 / 3.6,
)


def test_example_18_brussels_intermediate_terms() -> None:
    result = penman_monteith(BRUSSELS_WEATHER, BRUSSELS, BRUSSELS_DAY)
    terms = result.terms

    assert terms["es"] == pytest.approx(1.997, abs=0.001)
    assert terms["ea"] == pytest.approx(1.409, abs=0.001)
    assert terms["delta"] == pytest.approx(0.122, abs=0.001)
    assert terms["pressure"] == pytest.approx(100.1, abs=0.1)
    assert terms["gamma"] == pytest.approx(0.0666, abs=0.0001)
    assert terms["u2"] == pytest.approx(2.078, abs=0.001)
    assert terms["ra"] == pytest.approx(41.09, abs=0.01)
    assert terms["rso"] == pytest.approx(30.90, abs=0.01)
    assert terms["rns"] == pytest.approx(17.0, abs=0.01)
    assert terms["rnl"] == pytest.approx(3.71, abs=0.01)
    assert terms["rn"] == pytest.approx(13.28, abs=0.01)


def test_example_18_brussels_et0() -> None:
    result = penman_monteith(BRUSSELS_WEATHER, BRUSSELS, BRUSSELS_DAY)

    assert result.method is Et0Method.PENMAN_MONTEITH
    assert not result.is_estimate
    assert result.missing == ()
    assert result.et0_mm == pytest.approx(3.9, abs=0.05)


def test_example_8_extraterrestrial_radiation_southern_hemisphere() -> None:
    # 3 September, 20°S: Ra = 32.2 MJ m-2 day-1.
    assert extraterrestrial_radiation(-20, date(2026, 9, 3)) == pytest.approx(
        32.2, abs=0.05
    )


def test_polar_night_has_no_radiation() -> None:
    assert extraterrestrial_radiation(80, date(2026, 12, 21)) == pytest.approx(
        0.0, abs=1e-6
    )


def test_pressure_from_elevation_example_2() -> None:
    # Example 2: 1800 m -> P = 81.8 kPa.
    assert pressure_from_elevation(1800) == pytest.approx(81.8, abs=0.05)


def test_measured_pressure_is_used() -> None:
    weather = replace(BRUSSELS_WEATHER, pressure_kpa=95.0)
    result = penman_monteith(weather, BRUSSELS, BRUSSELS_DAY)

    assert result.terms["pressure"] == 95.0


def test_wind_at_2m_is_unchanged_at_2m() -> None:
    assert wind_at_2m(3.0, 2.0) == 3.0


def test_low_wind_is_limited_to_half_meter_per_second() -> None:
    weather = DailyWeather(
        tmax_c=21.5, tmin_c=12.3, rh_mean_pct=70, solar_mj_m2=20, wind_ms=0.0
    )
    result = penman_monteith(weather, Site(45, 100), BRUSSELS_DAY)

    assert result.terms["u2"] == 0.5


@pytest.mark.parametrize(
    ("rh_max", "rh_min", "rh_mean", "expected"),
    [
        (84, 63, None, 1.409),  # eq. 17
        (84, None, None, 1.431 * 0.84),  # eq. 18
        (None, None, 70.6, 1.997 * 0.706),  # eq. 19
        (None, 63, None, None),  # minimum alone is not enough
    ],
)
def test_actual_vapour_pressure_fallbacks(
    rh_max: float | None,
    rh_min: float | None,
    rh_mean: float | None,
    expected: float | None,
) -> None:
    weather = DailyWeather(
        tmax_c=21.5,
        tmin_c=12.3,
        rh_max_pct=rh_max,
        rh_min_pct=rh_min,
        rh_mean_pct=rh_mean,
    )
    ea = actual_vapour_pressure(weather)
    if expected is None:
        assert ea is None
    else:
        assert ea == pytest.approx(expected, abs=0.002)


def test_missing_inputs_are_reported() -> None:
    weather = DailyWeather(tmax_c=None, tmin_c=12.0)
    result = penman_monteith(weather, BRUSSELS, BRUSSELS_DAY)

    assert result.et0_mm is None
    assert result.method is None
    assert result.missing == ("tmax", "humidity", "solar_radiation", "wind")


def test_unusable_humidity_is_reported() -> None:
    weather = DailyWeather(
        tmax_c=21.5, tmin_c=12.3, rh_min_pct=63, solar_mj_m2=20, wind_ms=2
    )
    result = penman_monteith(weather, BRUSSELS, BRUSSELS_DAY)

    assert result.et0_mm is None
    assert result.missing == ("humidity",)


def test_et0_is_never_negative() -> None:
    # Cold, humid, dark day: Penman-Monteith can go slightly below zero.
    weather = DailyWeather(
        tmax_c=1.0,
        tmin_c=-1.0,
        rh_max_pct=100,
        rh_min_pct=100,
        solar_mj_m2=0.5,
        wind_ms=0.5,
    )
    result = penman_monteith(weather, Site(60, 0), date(2026, 12, 21))

    assert result.et0_mm == 0.0


def test_hargreaves_eq_52() -> None:
    result = hargreaves(BRUSSELS_WEATHER, BRUSSELS, BRUSSELS_DAY)
    expected = 0.0023 * (16.9 + 17.8) * (21.5 - 12.3) ** 0.5 * 41.09 * 0.408

    assert result.method is Et0Method.HARGREAVES
    assert result.is_estimate
    assert result.et0_mm == pytest.approx(expected, abs=0.01)


def test_hargreaves_needs_temperatures() -> None:
    result = hargreaves(DailyWeather(tmax_c=20, tmin_c=None), BRUSSELS, BRUSSELS_DAY)

    assert result.et0_mm is None
    assert result.missing == ("tmin",)


def test_compute_et0_prefers_penman_monteith() -> None:
    result = compute_et0(
        BRUSSELS_WEATHER, BRUSSELS, BRUSSELS_DAY, allow_hargreaves=True
    )

    assert result.method is Et0Method.PENMAN_MONTEITH


def test_compute_et0_without_fallback_stays_unknown() -> None:
    weather = DailyWeather(tmax_c=21.5, tmin_c=12.3, rh_mean_pct=70)
    result = compute_et0(weather, BRUSSELS, BRUSSELS_DAY, allow_hargreaves=False)

    assert result.et0_mm is None
    assert result.missing == ("solar_radiation", "wind")


def test_compute_et0_falls_back_to_hargreaves() -> None:
    weather = DailyWeather(tmax_c=21.5, tmin_c=12.3, rh_mean_pct=70)
    result = compute_et0(weather, BRUSSELS, BRUSSELS_DAY, allow_hargreaves=True)

    assert result.method is Et0Method.HARGREAVES
    assert result.et0_mm is not None
    # What Penman-Monteith lacked is kept for diagnostics.
    assert result.missing == ("solar_radiation", "wind")


def test_compute_et0_fallback_impossible_without_temperature() -> None:
    weather = DailyWeather(tmax_c=None, tmin_c=None, rh_mean_pct=70)
    result = compute_et0(weather, BRUSSELS, BRUSSELS_DAY, allow_hargreaves=True)

    assert result.et0_mm is None
    assert result.method is None
