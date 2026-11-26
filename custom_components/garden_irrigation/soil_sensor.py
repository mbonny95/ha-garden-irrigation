"""Soil moisture sensor of a zone (e.g. WH51): device-relative reading.

The percentage is not volumetric water content: it is only compared with
the user's own dry/wet thresholds and only ever produces warnings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from .model.recommendation import SoilSensorReading
from .settings import ZoneConfig

STALE_AFTER = timedelta(hours=6)


class SoilStatus(StrEnum):
    """Reading compared with the user's thresholds."""

    DRY = "dry"
    OK = "ok"
    WET = "wet"
    NO_THRESHOLDS = "no_thresholds"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SoilSensorState:
    """Current reading of a zone's soil moisture sensor."""

    entity_id: str
    value_pct: float | None
    status: SoilStatus
    last_reported: datetime | None
    dry_pct: float | None
    wet_pct: float | None

    @property
    def reading(self) -> SoilSensorReading | None:
        """Reading usable by the recommendation (fresh values only)."""
        if self.value_pct is None or self.status in (
            SoilStatus.STALE,
            SoilStatus.UNAVAILABLE,
        ):
            return None
        return SoilSensorReading(self.value_pct, self.dry_pct, self.wet_pct)


def read_soil_sensor(
    hass: HomeAssistant, zone: ZoneConfig, now: datetime
) -> SoilSensorState | None:
    """State of the zone's soil sensor, or None if the zone has none."""
    entity_id = zone.soil_moisture_entity
    if entity_id is None:
        return None
    dry, wet = zone.soil_moisture_dry, zone.soil_moisture_wet

    state = hass.states.get(entity_id)
    value: float | None = None
    if state is not None and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        try:
            value = float(state.state)
        except ValueError:
            value = None
    if state is None or value is None:
        return SoilSensorState(entity_id, None, SoilStatus.UNAVAILABLE, None, dry, wet)

    if now - state.last_reported > STALE_AFTER:
        status = SoilStatus.STALE
    elif dry is None and wet is None:
        status = SoilStatus.NO_THRESHOLDS
    elif dry is not None and value <= dry:
        status = SoilStatus.DRY
    elif wet is not None and value >= wet:
        status = SoilStatus.WET
    else:
        status = SoilStatus.OK
    return SoilSensorState(entity_id, value, status, state.last_reported, dry, wet)
