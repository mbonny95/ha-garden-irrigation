"""Soil reference data.

Available water capacity (AWC) is the midpoint of the θFC - θWP range in
FAO-56 Table 19, expressed in mm of water per m of soil depth.

`max_block_mm` is a practical cycle-and-soak guideline (how much water a
single block can apply before runoff becomes likely). It is NOT a FAO-56
value: it is a conservative starting point the user can override per zone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class SoilType:
    """Reference properties of a soil texture class."""

    key: str
    awc_mm_per_m: float
    max_block_mm: float


SOIL_CUSTOM: Final = "custom"

SOILS: Final[dict[str, SoilType]] = {
    soil.key: soil
    for soil in (
        SoilType("sand", 80.0, 12.0),
        SoilType("loamy_sand", 90.0, 10.0),
        SoilType("sandy_loam", 130.0, 8.0),
        SoilType("loam", 155.0, 6.0),
        SoilType("silt_loam", 160.0, 6.0),
        SoilType("silt", 180.0, 5.0),
        SoilType("silty_clay_loam", 155.0, 5.0),
        SoilType("silty_clay", 160.0, 4.0),
        SoilType("clay", 160.0, 4.0),
    )
}

DEFAULT_SOIL: Final = "loam"
