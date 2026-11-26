"""Binary sensor: does a zone need irrigation today."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import GardenIrrigationConfigEntry
from .entity import GardenIrrigationZoneEntity, messages_as_attributes

NEEDS_IRRIGATION = BinarySensorEntityDescription(
    key="needs_irrigation", translation_key="needs_irrigation"
)


class NeedsIrrigationSensor(GardenIrrigationZoneEntity, BinarySensorEntity):
    """On when the zone's deficit has reached its RAW."""

    @property
    def is_on(self) -> bool | None:
        """None (unknown) until the zone has a deficit."""
        return self.snapshot.recommendation.needs_irrigation

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Why, and what to keep in mind."""
        rec = self.snapshot.recommendation
        return {
            "reasons": messages_as_attributes(rec.reasons),
            "warnings": messages_as_attributes(rec.warnings),
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GardenIrrigationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One binary sensor per zone."""
    coordinator = entry.runtime_data.coordinator
    for zone_id in coordinator.zones:
        async_add_entities(
            [NeedsIrrigationSensor(coordinator, zone_id, NEEDS_IRRIGATION)],
            config_subentry_id=zone_id,
        )
