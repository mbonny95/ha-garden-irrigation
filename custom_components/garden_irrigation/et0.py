"""FAO-56 Penman-Monteith daily reference evapotranspiration (ET0) engine.

Milestone 3 scope only: pure computation from a `weather.DailyWeatherSnapshot`
(produced in Milestone 2) plus static location parameters. No per-zone water
balance, recommendation, scheduling or notification happens here (see
balance.py / recommendation.py / scheduler.py in later milestones).

Reference: Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998).
Crop evapotranspiration - Guidelines for computing crop water requirements.
FAO Irrigation and Drainage Paper 56, chapter 3 (equations as numbered there).

No automatic fallback for fundamental inputs: if temperature, humidity, wind,
or solar radiation are missing, ET0 is reported as incomplete/unknown with the
missing inputs listed, and a warning is logged. The only substitutions made
are the ones the FAO-56 method itself documents as acceptable approximations
when a specific (non-fundamental) refinement is unavailable:
  - actual vapor pressure (ea) from RHmean when RHmin/RHmax aren't both
    available (Eq. 19 vs Eq. 17 in FAO-56);
  - atmospheric pressure from altitude (Eq. 7) when a measured pressure isn't
    available, since altitude is always known (a required config value).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date

from .weather import DailyWeatherSnapshot

_LOGGER = logging.getLogger(__name__)

# Reference (FAO-56 grass) albedo - Eq. 38.
_ALBEDO = 0.23
# Stefan-Boltzmann constant [MJ K^-4 m^-2 day^-1] - Eq. 39.
_STEFAN_BOLTZMANN = 4.903e-9
# Solar constant [MJ m^-2 min^-1] - Eq. 28.
_SOLAR_CONSTANT = 0.0820
# Kelvin offset used specifically in the FAO-56 net longwave equation (Eq. 39).
_KELVIN_OFFSET_EQ39 = 273.16


@dataclass(frozen=True)
class ET0Result:
    """Daily ET0 plus every intermediate FAO-56 term, for diagnosis and tests.

    When a fundamental input is missing, `et0_mm` is None, `incomplete` is
    True, `missing_inputs` names what's absent, and every intermediate term is
    None as well (a half-computed result would be misleading, not merely
    "diagnostic").
    """

    day: date
    et0_mm: float | None
    incomplete: bool
    missing_inputs: tuple[str, ...]

    t_mean_c: float | None
    es_kpa: float | None
    ea_kpa: float | None
    delta_kpa_per_c: float | None
    gamma_kpa_per_c: float | None
    pressure_kpa: float | None
    pressure_source: str | None  # "measured" | "altitude_fallback"
    u2_ms: float | None
    rs_mj: float | None
    ra_mj: float | None
    rso_mj: float | None
    rns_mj: float | None
    rnl_mj: float | None
    rn_mj: float | None


def _incomplete_result(day: date, missing_inputs: tuple[str, ...]) -> ET0Result:
    _LOGGER.warning(
        "ET0 not computable for %s: missing fundamental input(s): %s",
        day.isoformat(),
        ", ".join(missing_inputs),
    )
    return ET0Result(
        day=day,
        et0_mm=None,
        incomplete=True,
        missing_inputs=missing_inputs,
        t_mean_c=None,
        es_kpa=None,
        ea_kpa=None,
        delta_kpa_per_c=None,
        gamma_kpa_per_c=None,
        pressure_kpa=None,
        pressure_source=None,
        u2_ms=None,
        rs_mj=None,
        ra_mj=None,
        rso_mj=None,
        rns_mj=None,
        rnl_mj=None,
        rn_mj=None,
    )


def _saturation_vapor_pressure_kpa(temp_c: float) -> float:
    """e°(T) [kPa] - FAO-56 Eq. 11."""
    return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))


def _slope_of_saturation_vapor_pressure_curve(temp_mean_c: float) -> float:
    """Delta [kPa/°C] - FAO-56 Eq. 13."""
    es_t = _saturation_vapor_pressure_kpa(temp_mean_c)
    return (4098.0 * es_t) / (temp_mean_c + 237.3) ** 2


def _psychrometric_constant(pressure_kpa: float) -> float:
    """gamma [kPa/°C] - FAO-56 Eq. 8."""
    return 0.000665 * pressure_kpa


def _pressure_from_altitude_kpa(altitude_m: float) -> float:
    """Atmospheric pressure [kPa] estimated from altitude - FAO-56 Eq. 7."""
    return 101.3 * math.pow((293.0 - 0.0065 * altitude_m) / 293.0, 5.26)


def _wind_speed_at_2m(wind_speed_kmh: float, anemometer_height_m: float) -> float:
    """Wind speed at 2m [m/s] - km/h -> m/s, then FAO-56 Eq. 47 if z != 2m."""
    wind_speed_ms = wind_speed_kmh / 3.6
    if anemometer_height_m == 2.0:
        return wind_speed_ms
    return wind_speed_ms * 4.87 / math.log(67.8 * anemometer_height_m - 5.42)


def _extraterrestrial_radiation_mj(latitude_deg: float, day_of_year: int) -> float:
    """Ra [MJ/m2/day] - FAO-56 Eq. 21 (via Eq. 23/24/25)."""
    lat_rad = math.radians(latitude_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    solar_declination = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    cos_sunset_hour_angle = -math.tan(lat_rad) * math.tan(solar_declination)
    # Clamp for numerical safety at extreme latitudes/declinations; not
    # expected to trigger for this integration's real-world usage.
    cos_sunset_hour_angle = max(-1.0, min(1.0, cos_sunset_hour_angle))
    sunset_hour_angle = math.acos(cos_sunset_hour_angle)
    return (
        (24 * 60 / math.pi)
        * _SOLAR_CONSTANT
        * dr
        * (
            sunset_hour_angle * math.sin(lat_rad) * math.sin(solar_declination)
            + math.cos(lat_rad)
            * math.cos(solar_declination)
            * math.sin(sunset_hour_angle)
        )
    )


def _net_longwave_radiation_mj(
    temp_max_c: float, temp_min_c: float, ea_kpa: float, rs_mj: float, rso_mj: float
) -> float:
    """Rnl [MJ/m2/day] - FAO-56 Eq. 39."""
    tmax_k4 = (temp_max_c + _KELVIN_OFFSET_EQ39) ** 4
    tmin_k4 = (temp_min_c + _KELVIN_OFFSET_EQ39) ** 4
    rs_rso = min(rs_mj / rso_mj, 1.0) if rso_mj > 0 else 1.0
    return (
        _STEFAN_BOLTZMANN
        * ((tmax_k4 + tmin_k4) / 2)
        * (0.34 - 0.14 * math.sqrt(max(ea_kpa, 0.0)))
        * (1.35 * rs_rso - 0.35)
    )


def compute_et0(
    snapshot: DailyWeatherSnapshot,
    *,
    latitude_deg: float,
    altitude_m: float,
    anemometer_height_m: float,
) -> ET0Result:
    """Compute daily FAO-56 Penman-Monteith ET0 from one weather snapshot.

    `snapshot` may be a still-in-progress day (WeatherAggregator.today_snapshot)
    or a finalized one (WeatherAggregator.get_finalized_day); this function
    does not care which, it just consumes whatever aggregates it's given.
    """
    missing: list[str] = []
    if snapshot.temp_min is None or snapshot.temp_max is None:
        missing.append("temperature")
    has_humidity_extremes = snapshot.rh_min is not None and snapshot.rh_max is not None
    if snapshot.rh_mean is None and not has_humidity_extremes:
        missing.append("humidity")
    if snapshot.wind_mean is None:
        missing.append("wind")
    if snapshot.solar_mj is None:
        missing.append("solar_radiation")

    if missing:
        return _incomplete_result(snapshot.day, tuple(missing))

    # mypy: the checks above guarantee these are not None from here on.
    temp_min = snapshot.temp_min
    temp_max = snapshot.temp_max
    assert temp_min is not None
    assert temp_max is not None
    wind_mean = snapshot.wind_mean
    assert wind_mean is not None
    rs_mj = snapshot.solar_mj
    assert rs_mj is not None

    t_mean = (temp_max + temp_min) / 2.0

    es_kpa = (
        _saturation_vapor_pressure_kpa(temp_max)
        + _saturation_vapor_pressure_kpa(temp_min)
    ) / 2.0

    if has_humidity_extremes:
        rh_min = snapshot.rh_min
        rh_max = snapshot.rh_max
        assert rh_min is not None
        assert rh_max is not None
        ea_kpa = (
            _saturation_vapor_pressure_kpa(temp_min) * (rh_max / 100.0)
            + _saturation_vapor_pressure_kpa(temp_max) * (rh_min / 100.0)
        ) / 2.0
    else:
        rh_mean = snapshot.rh_mean
        assert rh_mean is not None
        ea_kpa = (rh_mean / 100.0) * es_kpa

    delta = _slope_of_saturation_vapor_pressure_curve(t_mean)

    if snapshot.pressure_mean is not None:
        pressure_kpa = snapshot.pressure_mean / 10.0  # hPa -> kPa
        pressure_source = "measured"
    else:
        pressure_kpa = _pressure_from_altitude_kpa(altitude_m)
        pressure_source = "altitude_fallback"
    gamma = _psychrometric_constant(pressure_kpa)

    u2 = _wind_speed_at_2m(wind_mean, anemometer_height_m)

    day_of_year = snapshot.day.timetuple().tm_yday
    ra_mj = _extraterrestrial_radiation_mj(latitude_deg, day_of_year)
    rso_mj = (0.75 + 2e-5 * altitude_m) * ra_mj
    rns_mj = (1 - _ALBEDO) * rs_mj
    rnl_mj = _net_longwave_radiation_mj(temp_max, temp_min, ea_kpa, rs_mj, rso_mj)
    rn_mj = rns_mj - rnl_mj

    numerator = 0.408 * delta * rn_mj + gamma * (900.0 / (t_mean + 273.0)) * u2 * (
        es_kpa - ea_kpa
    )
    denominator = delta + gamma * (1 + 0.34 * u2)
    et0_mm = numerator / denominator

    return ET0Result(
        day=snapshot.day,
        et0_mm=et0_mm,
        incomplete=False,
        missing_inputs=(),
        t_mean_c=t_mean,
        es_kpa=es_kpa,
        ea_kpa=ea_kpa,
        delta_kpa_per_c=delta,
        gamma_kpa_per_c=gamma,
        pressure_kpa=pressure_kpa,
        pressure_source=pressure_source,
        u2_ms=u2,
        rs_mj=rs_mj,
        ra_mj=ra_mj,
        rso_mj=rso_mj,
        rns_mj=rns_mj,
        rnl_mj=rnl_mj,
        rn_mj=rn_mj,
    )
