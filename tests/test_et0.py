"""Tests for the garden_irrigation FAO-56 ET0 engine (Milestone 3).

Where a full daily ET0 figure is checked, the expected value is derived by an
independent re-implementation of the same public FAO-56 equations directly in
this file (not by importing et0.py's private helpers, and not by citing a
specific published worked example from memory) - this catches transcription
bugs in et0.py without any risk of misquoting a reference number.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from custom_components.garden_irrigation.et0 import compute_et0
from custom_components.garden_irrigation.weather import DailyWeatherSnapshot


def _snapshot(**overrides: object) -> DailyWeatherSnapshot:
    """A fully-populated snapshot, so individual fields can be knocked out."""
    defaults: dict[str, object] = {
        "day": date(2026, 6, 21),
        "temp_min": 15.0,
        "temp_max": 25.0,
        "temp_mean": 20.0,
        "rh_min": 40.0,
        "rh_max": 80.0,
        "rh_mean": 60.0,
        "pressure_mean": 1013.25,  # hPa
        "wind_mean": 10.0,  # km/h
        "wind_gust_max": 20.0,
        "solar_mj": 20.0,  # MJ/m2/day
        "rain_mm": 0.0,
    }
    defaults.update(overrides)
    return DailyWeatherSnapshot(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Unit conversions: wind km/h -> m/s (+2m correction), pressure hPa -> kPa
# ---------------------------------------------------------------------------


def test_wind_speed_kmh_to_ms_no_correction_at_2m() -> None:
    result = compute_et0(
        _snapshot(wind_mean=36.0),  # 36 km/h = 10 m/s exactly
        latitude_deg=45.0,
        altitude_m=116.0,
        anemometer_height_m=2.0,
    )
    assert result.u2_ms == pytest.approx(10.0)


def test_wind_speed_corrected_to_2m_from_taller_anemometer() -> None:
    anemometer_height_m = 3.0
    wind_kmh = 36.0
    result = compute_et0(
        _snapshot(wind_mean=wind_kmh),
        latitude_deg=45.0,
        altitude_m=116.0,
        anemometer_height_m=anemometer_height_m,
    )
    uz = wind_kmh / 3.6
    expected_u2 = uz * 4.87 / math.log(67.8 * anemometer_height_m - 5.42)
    assert expected_u2 < uz  # FAO-56 Eq. 47 always reduces wind measured above 2m
    assert result.u2_ms == pytest.approx(expected_u2)


def test_pressure_measured_hpa_converted_to_kpa() -> None:
    result = compute_et0(
        _snapshot(pressure_mean=1013.25),
        latitude_deg=45.0,
        altitude_m=116.0,
        anemometer_height_m=2.0,
    )
    assert result.pressure_source == "measured"
    assert result.pressure_kpa == pytest.approx(101.325)


def test_pressure_falls_back_to_altitude_when_not_measured() -> None:
    altitude_m = 116.0
    result = compute_et0(
        _snapshot(pressure_mean=None),
        latitude_deg=45.0,
        altitude_m=altitude_m,
        anemometer_height_m=2.0,
    )
    expected_pressure_kpa = 101.3 * ((293.0 - 0.0065 * altitude_m) / 293.0) ** 5.26
    assert result.pressure_source == "altitude_fallback"
    assert result.pressure_kpa == pytest.approx(expected_pressure_kpa)
    # A missing measured pressure is NOT a fundamental input: ET0 must still
    # compute (this is a documented FAO-56 approximation, not a forbidden
    # automatic fallback for a missing fundamental input).
    assert result.incomplete is False
    assert result.et0_mm is not None


def test_ea_falls_back_to_rh_mean_when_extremes_are_missing() -> None:
    """Documented FAO-56 approximation (Eq. 19 vs Eq. 17), not a forbidden
    fallback: humidity is still usable, just less precise, from rh_mean
    alone."""
    temp_min, temp_max, rh_mean = 15.0, 25.0, 60.0
    result = compute_et0(
        _snapshot(
            temp_min=temp_min,
            temp_max=temp_max,
            rh_min=None,
            rh_max=None,
            rh_mean=rh_mean,
        ),
        latitude_deg=45.0,
        altitude_m=116.0,
        anemometer_height_m=2.0,
    )

    def es(t: float) -> float:
        return 0.6108 * math.exp((17.27 * t) / (t + 237.3))

    es_val = (es(temp_max) + es(temp_min)) / 2.0
    expected_ea = (rh_mean / 100.0) * es_val

    assert result.incomplete is False
    assert result.ea_kpa == pytest.approx(expected_ea)


# ---------------------------------------------------------------------------
# Radiative terms: Ra / Rso / Rns / Rnl / Rn, MJ integration
# ---------------------------------------------------------------------------


def test_extraterrestrial_and_clear_sky_radiation() -> None:
    latitude_deg = 45.0
    altitude_m = 116.0
    day_of_year = date(2026, 6, 21).timetuple().tm_yday

    result = compute_et0(
        _snapshot(),
        latitude_deg=latitude_deg,
        altitude_m=altitude_m,
        anemometer_height_m=2.0,
    )

    lat_rad = math.radians(latitude_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    decl = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    ws = math.acos(-math.tan(lat_rad) * math.tan(decl))
    expected_ra = (
        (24 * 60 / math.pi)
        * 0.0820
        * dr
        * (
            ws * math.sin(lat_rad) * math.sin(decl)
            + math.cos(lat_rad) * math.cos(decl) * math.sin(ws)
        )
    )
    expected_rso = (0.75 + 2e-5 * altitude_m) * expected_ra

    assert result.ra_mj == pytest.approx(expected_ra)
    assert result.rso_mj == pytest.approx(expected_rso)


def test_net_shortwave_and_longwave_radiation() -> None:
    rs_mj = 20.0
    result = compute_et0(
        _snapshot(solar_mj=rs_mj),
        latitude_deg=45.0,
        altitude_m=116.0,
        anemometer_height_m=2.0,
    )

    expected_rns = (1 - 0.23) * rs_mj
    assert result.rns_mj == pytest.approx(expected_rns)

    tmax_k4 = (25.0 + 273.16) ** 4
    tmin_k4 = (15.0 + 273.16) ** 4
    assert result.rso_mj is not None
    rs_rso = min(rs_mj / result.rso_mj, 1.0)
    assert result.ea_kpa is not None
    expected_rnl = (
        4.903e-9
        * ((tmax_k4 + tmin_k4) / 2)
        * (0.34 - 0.14 * math.sqrt(result.ea_kpa))
        * (1.35 * rs_rso - 0.35)
    )
    assert result.rnl_mj == pytest.approx(expected_rnl)
    assert result.rn_mj == pytest.approx(expected_rns - expected_rnl)


# ---------------------------------------------------------------------------
# Full nominal case: independent re-derivation of the whole Penman-Monteith
# equation, to validate that every term is wired together correctly.
# ---------------------------------------------------------------------------


def test_et0_full_nominal_case_matches_independent_derivation() -> None:
    latitude_deg = 45.0
    altitude_m = 116.0
    anemometer_height_m = 2.0
    temp_min, temp_max = 15.0, 25.0
    rh_min, rh_max = 40.0, 80.0
    pressure_hpa = 1013.25
    wind_kmh = 10.0
    rs_mj = 20.0
    day = date(2026, 6, 21)

    result = compute_et0(
        _snapshot(
            temp_min=temp_min,
            temp_max=temp_max,
            rh_min=rh_min,
            rh_max=rh_max,
            pressure_mean=pressure_hpa,
            wind_mean=wind_kmh,
            solar_mj=rs_mj,
            day=day,
        ),
        latitude_deg=latitude_deg,
        altitude_m=altitude_m,
        anemometer_height_m=anemometer_height_m,
    )

    def es(t: float) -> float:
        return 0.6108 * math.exp((17.27 * t) / (t + 237.3))

    t_mean = (temp_max + temp_min) / 2.0
    es_val = (es(temp_max) + es(temp_min)) / 2.0
    ea_val = (es(temp_min) * (rh_max / 100.0) + es(temp_max) * (rh_min / 100.0)) / 2.0
    delta = (4098.0 * es(t_mean)) / (t_mean + 237.3) ** 2
    pressure_kpa = pressure_hpa / 10.0
    gamma = 0.000665 * pressure_kpa
    u2 = wind_kmh / 3.6  # anemometer already at 2m

    day_of_year = day.timetuple().tm_yday
    lat_rad = math.radians(latitude_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    decl = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    ws = math.acos(-math.tan(lat_rad) * math.tan(decl))
    ra = (
        (24 * 60 / math.pi)
        * 0.0820
        * dr
        * (
            ws * math.sin(lat_rad) * math.sin(decl)
            + math.cos(lat_rad) * math.cos(decl) * math.sin(ws)
        )
    )
    rso = (0.75 + 2e-5 * altitude_m) * ra
    rns = (1 - 0.23) * rs_mj
    tmax_k4 = (temp_max + 273.16) ** 4
    tmin_k4 = (temp_min + 273.16) ** 4
    rs_rso = min(rs_mj / rso, 1.0)
    rnl = (
        4.903e-9
        * ((tmax_k4 + tmin_k4) / 2)
        * (0.34 - 0.14 * math.sqrt(ea_val))
        * (1.35 * rs_rso - 0.35)
    )
    rn = rns - rnl

    numerator = 0.408 * delta * rn + gamma * (900.0 / (t_mean + 273.0)) * u2 * (
        es_val - ea_val
    )
    denominator = delta + gamma * (1 + 0.34 * u2)
    expected_et0 = numerator / denominator

    assert result.incomplete is False
    assert result.et0_mm == pytest.approx(expected_et0, rel=1e-9)
    # Sanity: a mid-latitude clear early-summer day should be a plausible,
    # strictly positive daily ET0 (loose bound, just guards against gross
    # unit errors such as a forgotten km/h->m/s conversion).
    assert 0.0 < result.et0_mm < 15.0


# ---------------------------------------------------------------------------
# Missing fundamental inputs: no automatic fallback, explicit "incomplete"
# ---------------------------------------------------------------------------


def test_missing_temperature_makes_result_incomplete() -> None:
    result = compute_et0(
        _snapshot(temp_min=None),
        latitude_deg=45.0,
        altitude_m=116.0,
        anemometer_height_m=2.0,
    )
    assert result.incomplete is True
    assert result.missing_inputs == ("temperature",)
    assert result.et0_mm is None


def test_missing_humidity_makes_result_incomplete() -> None:
    result = compute_et0(
        _snapshot(rh_min=None, rh_max=None, rh_mean=None),
        latitude_deg=45.0,
        altitude_m=116.0,
        anemometer_height_m=2.0,
    )
    assert result.incomplete is True
    assert result.missing_inputs == ("humidity",)
    assert result.et0_mm is None


def test_partial_humidity_extremes_without_mean_is_still_incomplete() -> None:
    """Only one of rh_min/rh_max present, and no rh_mean to fall back on."""
    result = compute_et0(
        _snapshot(rh_min=40.0, rh_max=None, rh_mean=None),
        latitude_deg=45.0,
        altitude_m=116.0,
        anemometer_height_m=2.0,
    )
    assert result.incomplete is True
    assert result.missing_inputs == ("humidity",)


def test_missing_wind_makes_result_incomplete() -> None:
    result = compute_et0(
        _snapshot(wind_mean=None),
        latitude_deg=45.0,
        altitude_m=116.0,
        anemometer_height_m=2.0,
    )
    assert result.incomplete is True
    assert result.missing_inputs == ("wind",)
    assert result.et0_mm is None


def test_missing_solar_radiation_makes_result_incomplete() -> None:
    result = compute_et0(
        _snapshot(solar_mj=None),
        latitude_deg=45.0,
        altitude_m=116.0,
        anemometer_height_m=2.0,
    )
    assert result.incomplete is True
    assert result.missing_inputs == ("solar_radiation",)
    assert result.et0_mm is None


def test_all_fundamental_inputs_missing_lists_all_of_them() -> None:
    result = compute_et0(
        _snapshot(
            temp_min=None,
            temp_max=None,
            rh_min=None,
            rh_max=None,
            rh_mean=None,
            wind_mean=None,
            solar_mj=None,
        ),
        latitude_deg=45.0,
        altitude_m=116.0,
        anemometer_height_m=2.0,
    )
    assert result.incomplete is True
    assert result.missing_inputs == (
        "temperature",
        "humidity",
        "wind",
        "solar_radiation",
    )
    assert result.et0_mm is None


def test_incomplete_result_has_no_partial_intermediate_terms() -> None:
    """No sneaky partial computation: everything is None, not just et0_mm.

    This guards against an unintended "smart" fallback silently computing
    some terms from the available subset of inputs.
    """
    result = compute_et0(
        _snapshot(solar_mj=None),
        latitude_deg=45.0,
        altitude_m=116.0,
        anemometer_height_m=2.0,
    )
    assert result.t_mean_c is None
    assert result.es_kpa is None
    assert result.ea_kpa is None
    assert result.delta_kpa_per_c is None
    assert result.gamma_kpa_per_c is None
    assert result.pressure_kpa is None
    assert result.pressure_source is None
    assert result.u2_ms is None
    assert result.rs_mj is None
    assert result.ra_mj is None
    assert result.rso_mj is None
    assert result.rns_mj is None
    assert result.rnl_mj is None
    assert result.rn_mj is None
