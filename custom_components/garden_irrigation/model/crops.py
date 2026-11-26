"""Crop reference data: monthly Kc profiles and depletion fraction p.

Cool-season turf (e.g. Festuca arundinacea): FAO-56 Table 12 gives
Kc ≈ 0.90-0.95 during active growth and Table 22 gives p = 0.40. The reduced
cold-season values are a starting assumption to be validated in the field;
the user can always switch to a custom 12-month profile.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

CROP_COOL_SEASON_TURF: Final = "cool_season_turf"
CROP_CUSTOM: Final = "custom"

KC_PROFILES: Final[dict[str, tuple[float, ...]]] = {
    #                       Jan   Feb   Mar   Apr   May   Jun   Jul   Aug   Sep   Oct   Nov   Dec
    CROP_COOL_SEASON_TURF: (0.70, 0.70, 0.80, 0.95, 0.95, 0.95, 0.95, 0.95, 0.95, 0.80, 0.70, 0.70),
}  # fmt: skip

DEFAULT_CROP: Final = CROP_COOL_SEASON_TURF
DEFAULT_DEPLETION_FRACTION: Final = 0.40
DEFAULT_ROOT_DEPTH_MM: Final = 150.0


def kc_for_month(profile: Sequence[float], month: int) -> float:
    """Return the Kc of `month` (1 = January) from a 12-value profile."""
    if len(profile) != 12:
        raise ValueError(f"Kc profile must have 12 values, got {len(profile)}")
    if not 1 <= month <= 12:
        raise ValueError(f"month must be in 1..12, got {month}")
    return float(profile[month - 1])
