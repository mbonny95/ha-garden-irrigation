"""Binary sensor platform for garden_irrigation.

Milestone 7 added `needs_irrigation_{zone}` (from recommendation.py's
finalized, persisted-balance-based recommendation) and
`weekly_cap_reached_{zone}` (already exposed by balance.py's
ZoneBalanceResult, no new logic needed). Milestone 9 adds
`irrigation_in_progress`: a single, zone-agnostic, purely declarative sensor
reflecting `coordinator.cycle_zone` (set/cleared by button.py's start/end
cycle buttons) - never inferred from any other sensor. `data_stale` (the
staleness-threshold monitor built alongside notify.py in M8) has no
dedicated binary_sensor - M8 exposed it as a repair issue instead, and adding
one now is out of scope for M9.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .balance import ZoneBalanceResult
from .const import (
    CONF_ZONE1_NAME,
    CONF_ZONE2_NAME,
    DEFAULT_ZONE1_NAME,
    DEFAULT_ZONE2_NAME,
    DOMAIN,
    ZONE_1,
    ZONES,
)
from .coordinator import GardenIrrigationCoordinator
from .entity import GardenIrrigationEntity
from .recommendation import ZoneRecommendationBundle


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the garden_irrigation binary_sensor platform."""
    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = [
        IrrigationInProgressSensor(coordinator, entry)
    ]
    for zone_id in ZONES:
        entities.extend(
            [
                NeedsIrrigationZoneSensor(coordinator, entry, zone_id),
                WeeklyCapReachedZoneSensor(coordinator, entry, zone_id),
            ]
        )
    async_add_entities(entities)


def _zone_name(entry: ConfigEntry, zone_id: str) -> str:
    """Return the user-configured display name for `zone_id`.

    Re-implemented here rather than imported from sensor.py (private helper,
    and sensor.py is out of scope to touch in M7).
    """
    if zone_id == ZONE_1:
        return str(entry.data.get(CONF_ZONE1_NAME, DEFAULT_ZONE1_NAME))
    return str(entry.data.get(CONF_ZONE2_NAME, DEFAULT_ZONE2_NAME))


class _ZoneBinarySensor(GardenIrrigationEntity, BinarySensorEntity):
    """Shared base for the per-zone binary sensors in this platform."""

    def __init__(
        self,
        coordinator: GardenIrrigationCoordinator,
        entry: ConfigEntry,
        zone_id: str,
        key: str,
    ) -> None:
        """Initialize with a per-zone unique_id and translation placeholder."""
        super().__init__(coordinator, entry)
        self.zone_id = zone_id
        self._attr_unique_id = f"{entry.entry_id}_{key}_{zone_id}"
        self._attr_translation_key = key
        self._attr_translation_placeholders = {"zone_name": _zone_name(entry, zone_id)}

    def _balance_result(self) -> ZoneBalanceResult | None:
        data = self.coordinator.data
        if not data:
            return None
        balance: dict[str, ZoneBalanceResult] = data.get("balance", {})
        return balance.get(self.zone_id)


class NeedsIrrigationZoneSensor(_ZoneBinarySensor):
    """Whether the zone's deficit is at/above RAW and no hard limit blocks it.

    Reflects the FINALIZED recommendation (built from the persisted balance
    for the most recently completed day), not the 20:00 preview - see
    recommendation.py. `is_on` is None (HA state "unknown") when the
    underlying data isn't ready yet (pending/ET0 unavailable) - never a
    guessed True/False.
    """

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zone_id: str
    ) -> None:
        """Initialize the per-zone needs_irrigation sensor."""
        super().__init__(coordinator, entry, zone_id, "needs_irrigation")

    def _recommendation_bundle(self) -> ZoneRecommendationBundle | None:
        data = self.coordinator.data
        if not data:
            return None
        recommendation: dict[str, ZoneRecommendationBundle] = data.get(
            "recommendation", {}
        )
        return recommendation.get(self.zone_id)

    @property
    def is_on(self) -> bool | None:
        """True if irrigation is currently recommended for this zone."""
        bundle = self._recommendation_bundle()
        if bundle is None:
            return None
        return bundle.final.needs_irrigation

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Explanatory reasons/limits/warnings behind the current state."""
        bundle = self._recommendation_bundle()
        if bundle is None:
            return None
        final = bundle.final
        return {
            "ready": final.ready,
            "reasons": list(final.reasons),
            "limits_applied": list(final.limits_applied),
            "warnings": list(final.warnings),
            "recommended_mm": final.recommended_mm,
            "wh51_status": final.wh51_status,
            "wh51_calibrated": final.wh51_calibrated,
            "preview_needs_irrigation": bundle.preview.needs_irrigation,
        }


class WeeklyCapReachedZoneSensor(_ZoneBinarySensor):
    """Whether the zone's sliding 7-day recorded-irrigation cap is reached.

    Directly reflects balance.py's own ZoneBalanceResult.weekly_cap_reached -
    no new logic. Governs only user-recorded irrigation, never effective rain
    (see CLAUDE.md).
    """

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zone_id: str
    ) -> None:
        """Initialize the per-zone weekly_cap_reached sensor."""
        super().__init__(coordinator, entry, zone_id, "weekly_cap_reached")

    @property
    def is_on(self) -> bool | None:
        """True once the 7-day recorded-irrigation cap has been reached."""
        result = self._balance_result()
        return result.weekly_cap_reached if result is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """The 7-day recorded total and the configured cap."""
        result = self._balance_result()
        if result is None:
            return None
        return {
            "irrigation_7d_mm": result.irrigation_7d_mm,
            "weekly_cap_mm": result.weekly_cap_mm,
        }


class IrrigationInProgressSensor(GardenIrrigationEntity, BinarySensorEntity):
    """Whether a manual cycle has been declared active (button.py).

    Purely declarative: `is_on` reflects `coordinator.cycle_zone` only, never
    inferred from weather/soil/recommendation data. Elapsed time is exposed
    as an attribute here rather than a separate sensor.py entity (out of
    scope to touch in M9) - never used to prefill the record_irrigation
    form's minutes field (CLAUDE.md), which this entity has no access to
    anyway.
    """

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize with a stable unique_id derived from the config entry."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_irrigation_in_progress"
        self._attr_translation_key = "irrigation_in_progress"

    @property
    def is_on(self) -> bool:
        """True while a cycle is declared active for any zone."""
        return self.coordinator.cycle_zone is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """The active zone, its start time, and elapsed minutes so far."""
        zone_id = self.coordinator.cycle_zone
        if zone_id is None:
            return None
        started_at = self.coordinator.cycle_started_at
        elapsed_minutes: float | None = None
        if started_at is not None:
            now: datetime = dt_util.now()
            elapsed_minutes = (now - started_at).total_seconds() / 60.0
        return {
            "zone": zone_id,
            "started_at": started_at.isoformat() if started_at else None,
            "elapsed_minutes": elapsed_minutes,
        }
