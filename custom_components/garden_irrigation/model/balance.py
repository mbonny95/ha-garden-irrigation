"""FAO-56 root-zone soil water balance, single crop coefficient (chapter 8).

Depletion (deficit) is tracked in mm below field capacity: 0 = field
capacity, TAW = wilting point. Deep percolation and runoff are implicit:
water beyond what refills the root zone is simply not counted.
"""

from __future__ import annotations

from dataclasses import dataclass

P_MIN = 0.1  # FAO-56 limits the adjusted p to 0.1 <= p <= 0.8
P_MAX = 0.8


@dataclass(frozen=True, slots=True)
class SoilWater:
    """Water holding capacity of a zone's root zone (mm)."""

    taw_mm: float
    raw_mm: float


def total_available_water(root_depth_mm: float, awc_mm_per_m: float) -> float:
    """TAW = AWC × Zr (eq. 82, with AWC = 1000 (θFC − θWP))."""
    return root_depth_mm / 1000.0 * awc_mm_per_m


def depletion_fraction(p_table: float, etc_mm: float | None, *, adjust: bool) -> float:
    """p, optionally adjusted for the evaporative demand (FAO-56 Table 22 note).

    p = p_table + 0.04 (5 − ETc), limited to [0.1, 0.8]. Without adjustment
    (or without ETc) the table value is returned unchanged.
    """
    if not adjust or etc_mm is None:
        return p_table
    return min(max(p_table + 0.04 * (5.0 - etc_mm), P_MIN), P_MAX)


def soil_water(root_depth_mm: float, awc_mm_per_m: float, p: float) -> SoilWater:
    """TAW and RAW = p × TAW (eq. 83)."""
    taw = total_available_water(root_depth_mm, awc_mm_per_m)
    return SoilWater(taw_mm=taw, raw_mm=p * taw)


def effective_rain(
    rain_mm: float,
    *,
    factor: float,
    threshold_mm: float,
    prev_deficit_mm: float,
    etc_mm: float,
) -> float:
    """Rain that actually refills the root zone.

    Rain below `threshold_mm` is lost to interception/evaporation. Otherwise
    `factor` of it counts, capped at what the soil can store that day.
    """
    if rain_mm < threshold_mm or rain_mm <= 0:
        return 0.0
    return min(rain_mm * factor, prev_deficit_mm + etc_mm)


@dataclass(frozen=True, slots=True)
class DayBalance:
    """Outcome of one day of the water balance (mm)."""

    etc_mm: float | None  # None when ET0 was unknown
    effective_rain_mm: float
    irrigation_mm: float
    deficit_mm: float


def apply_day(
    prev_deficit_mm: float,
    *,
    et0_mm: float | None,
    kc: float,
    rain_mm: float,
    irrigation_mm: float,
    taw_mm: float,
    rain_factor: float,
    rain_threshold_mm: float,
) -> DayBalance:
    """Advance the deficit by one closed day (eq. 85, single Kc).

    deficit = clamp(prev + ETc − effective rain − irrigation, 0, TAW)

    With ET0 unknown the day is still applied with ETc = 0, so the rain and
    irrigation of that day are not lost; the caller flags it as incomplete.
    """
    etc = et0_mm * kc if et0_mm is not None else None
    water_use = etc if etc is not None else 0.0
    eff_rain = effective_rain(
        rain_mm,
        factor=rain_factor,
        threshold_mm=rain_threshold_mm,
        prev_deficit_mm=prev_deficit_mm,
        etc_mm=water_use,
    )
    deficit = prev_deficit_mm + water_use - eff_rain - irrigation_mm
    return DayBalance(
        etc_mm=etc,
        effective_rain_mm=eff_rain,
        irrigation_mm=irrigation_mm,
        deficit_mm=min(max(deficit, 0.0), taw_mm),
    )


def current_deficit(closed_day_deficit_mm: float, irrigation_today_mm: float) -> float:
    """Deficit right now: last closed day minus irrigation recorded today."""
    return max(closed_day_deficit_mm - irrigation_today_mm, 0.0)
