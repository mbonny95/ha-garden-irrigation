"""FAO-56 daily reference evapotranspiration (ET0).

Equation numbers refer to FAO Irrigation and Drainage Paper No. 56, Allen et
al. (1998). Daily time step, soil heat flux G = 0 (eq. 42).

Penman-Monteith (eq. 6) needs air temperature extremes, humidity, solar
radiation and wind. Hargreaves (eq. 52) needs only temperature extremes and
is used only when the caller allows it and Penman-Monteith inputs are
missing; its result is always flagged as an estimate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

SOLAR_CONSTANT = 0.0820  # MJ m-2 min-1
STEFAN_BOLTZMANN = 4.903e-9  # MJ K-4 m-2 day-1
ALBEDO = 0.23  # hypothetical grass reference crop
MJ_TO_MM = 0.408  # 1 / latent heat of vaporization (λ = 2.45 MJ kg-1)
MIN_WIND_2M = 0.5  # m/s, lower limit recommended by FAO-56 (chapter 3)


class Et0Method(StrEnum):
    """How ET0 was obtained."""

    PENMAN_MONTEITH = "penman_monteith"
    HARGREAVES = "hargreaves"


@dataclass(frozen=True, slots=True)
class Site:
    """Fixed properties of the weather station location."""

    latitude_deg: float
    elevation_m: float
    anemometer_height_m: float = 2.0


@dataclass(frozen=True, slots=True)
class DailyWeather:
    """Aggregated weather of one day, in FAO-56 units.

    Missing inputs are None. Humidity can be given as extremes (best), as
    maximum only, or as mean (eqs. 17, 18, 19).
    """

    tmax_c: float | None
    tmin_c: float | None
    rh_max_pct: float | None = None
    rh_min_pct: float | None = None
    rh_mean_pct: float | None = None
    solar_mj_m2: float | None = None  # incoming shortwave Rs, daily total
    wind_ms: float | None = None  # mean speed at the anemometer height
    pressure_kpa: float | None = None


@dataclass(frozen=True, slots=True)
class Et0Result:
    """ET0 of one day, or the inputs that prevented computing it."""

    et0_mm: float | None
    method: Et0Method | None
    missing: tuple[str, ...] = ()
    terms: dict[str, float] = field(default_factory=dict)

    @property
    def is_estimate(self) -> bool:
        """True when the less accurate Hargreaves method was used."""
        return self.method is Et0Method.HARGREAVES


# --- Atmospheric parameters ---------------------------------------------------------


def pressure_from_elevation(elevation_m: float) -> float:
    """Atmospheric pressure in kPa from elevation (eq. 7)."""
    return 101.3 * math.pow((293.0 - 0.0065 * elevation_m) / 293.0, 5.26)


def psychrometric_constant(pressure_kpa: float) -> float:
    """γ in kPa °C-1 (eq. 8)."""
    return 0.665e-3 * pressure_kpa


def saturation_vapour_pressure(temp_c: float) -> float:
    """e°(T) in kPa (eq. 11)."""
    return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def vapour_pressure_slope(temp_c: float) -> float:
    """Δ in kPa °C-1 (eq. 13)."""
    return 4098.0 * saturation_vapour_pressure(temp_c) / (temp_c + 237.3) ** 2


def actual_vapour_pressure(weather: DailyWeather) -> float | None:
    """ea in kPa from the best available humidity data (eqs. 17, 18, 19)."""
    if weather.tmax_c is None or weather.tmin_c is None:
        return None
    e_tmax = saturation_vapour_pressure(weather.tmax_c)
    e_tmin = saturation_vapour_pressure(weather.tmin_c)
    if weather.rh_max_pct is not None and weather.rh_min_pct is not None:
        return (e_tmin * weather.rh_max_pct + e_tmax * weather.rh_min_pct) / 200.0
    if weather.rh_max_pct is not None:
        return e_tmin * weather.rh_max_pct / 100.0
    if weather.rh_mean_pct is not None:
        return weather.rh_mean_pct / 100.0 * (e_tmax + e_tmin) / 2.0
    return None


def wind_at_2m(wind_ms: float, height_m: float) -> float:
    """Convert wind speed measured at `height_m` to 2 m (eq. 47)."""
    if math.isclose(height_m, 2.0):
        return wind_ms
    return wind_ms * 4.87 / math.log(67.8 * height_m - 5.42)


# --- Radiation ----------------------------------------------------------------------


def extraterrestrial_radiation(latitude_deg: float, day: date) -> float:
    """Ra in MJ m-2 day-1 (eqs. 21-25)."""
    doy = day.timetuple().tm_yday
    phi = math.radians(latitude_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    # Clamped for polar day/night, where eq. 25 has no real solution.
    omega_s = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    return (
        24
        * 60
        / math.pi
        * SOLAR_CONSTANT
        * dr
        * (
            omega_s * math.sin(phi) * math.sin(delta)
            + math.cos(phi) * math.cos(delta) * math.sin(omega_s)
        )
    )


def clear_sky_radiation(ra: float, elevation_m: float) -> float:
    """Rso in MJ m-2 day-1 (eq. 37)."""
    return (0.75 + 2e-5 * elevation_m) * ra


def net_longwave_radiation(
    tmax_c: float, tmin_c: float, ea_kpa: float, rs: float, rso: float
) -> float:
    """Rnl in MJ m-2 day-1 (eq. 39). Rs/Rso is limited to 1.0."""
    ratio = min(rs / rso, 1.0) if rso > 0 else 1.0
    sigma_t4 = (
        STEFAN_BOLTZMANN * ((tmax_c + 273.16) ** 4 + (tmin_c + 273.16) ** 4) / 2.0
    )
    return sigma_t4 * (0.34 - 0.14 * math.sqrt(ea_kpa)) * (1.35 * ratio - 0.35)


# --- ET0 ------------------------------------------------------------------------------


def penman_monteith(weather: DailyWeather, site: Site, day: date) -> Et0Result:
    """Daily ET0 with FAO-56 Penman-Monteith (eq. 6)."""
    missing = _missing_penman_monteith(weather)
    ea = actual_vapour_pressure(weather)
    if missing or ea is None:
        return Et0Result(None, None, missing or ("humidity",))
    # Narrowed by _missing_penman_monteith.
    assert weather.tmax_c is not None and weather.tmin_c is not None
    assert weather.solar_mj_m2 is not None and weather.wind_ms is not None

    tmax, tmin = weather.tmax_c, weather.tmin_c
    tmean = (tmax + tmin) / 2.0
    es = (saturation_vapour_pressure(tmax) + saturation_vapour_pressure(tmin)) / 2.0
    delta = vapour_pressure_slope(tmean)
    pressure = (
        weather.pressure_kpa
        if weather.pressure_kpa is not None
        else pressure_from_elevation(site.elevation_m)
    )
    gamma = psychrometric_constant(pressure)
    u2 = max(wind_at_2m(weather.wind_ms, site.anemometer_height_m), MIN_WIND_2M)

    ra = extraterrestrial_radiation(site.latitude_deg, day)
    rso = clear_sky_radiation(ra, site.elevation_m)
    rs = weather.solar_mj_m2
    rns = (1 - ALBEDO) * rs
    rnl = net_longwave_radiation(tmax, tmin, ea, rs, rso)
    rn = rns - rnl

    numerator = 0.408 * delta * rn + gamma * 900.0 / (tmean + 273.0) * u2 * (es - ea)
    denominator = delta + gamma * (1 + 0.34 * u2)
    et0 = max(numerator / denominator, 0.0)

    return Et0Result(
        et0,
        Et0Method.PENMAN_MONTEITH,
        terms={
            "es": es,
            "ea": ea,
            "delta": delta,
            "pressure": pressure,
            "gamma": gamma,
            "u2": u2,
            "ra": ra,
            "rso": rso,
            "rns": rns,
            "rnl": rnl,
            "rn": rn,
        },
    )


def hargreaves(weather: DailyWeather, site: Site, day: date) -> Et0Result:
    """Daily ET0 with the Hargreaves equation (eq. 52)."""
    if weather.tmax_c is None or weather.tmin_c is None:
        return Et0Result(None, None, _missing_temperature(weather))
    tmax, tmin = weather.tmax_c, weather.tmin_c
    ra = extraterrestrial_radiation(site.latitude_deg, day)
    tmean = (tmax + tmin) / 2.0
    et0 = 0.0023 * (tmean + 17.8) * math.sqrt(max(tmax - tmin, 0.0)) * ra * MJ_TO_MM
    return Et0Result(max(et0, 0.0), Et0Method.HARGREAVES, terms={"ra": ra})


def compute_et0(
    weather: DailyWeather, site: Site, day: date, *, allow_hargreaves: bool
) -> Et0Result:
    """Penman-Monteith, or Hargreaves when allowed and PM inputs are missing."""
    result = penman_monteith(weather, site, day)
    if result.et0_mm is not None or not allow_hargreaves:
        return result
    fallback = hargreaves(weather, site, day)
    if fallback.et0_mm is None:
        return result
    # Keep the list of what Penman-Monteith lacked, for diagnostics.
    return Et0Result(fallback.et0_mm, fallback.method, result.missing, fallback.terms)


def _missing_temperature(weather: DailyWeather) -> tuple[str, ...]:
    return tuple(
        name
        for name, value in (("tmax", weather.tmax_c), ("tmin", weather.tmin_c))
        if value is None
    )


def _missing_penman_monteith(weather: DailyWeather) -> tuple[str, ...]:
    missing = list(_missing_temperature(weather))
    if (
        weather.rh_max_pct is None
        and weather.rh_min_pct is None
        and weather.rh_mean_pct is None
    ):
        missing.append("humidity")
    if weather.solar_mj_m2 is None:
        missing.append("solar_radiation")
    if weather.wind_ms is None:
        missing.append("wind")
    return tuple(missing)
