"""Base entities: one device for the installation, one per zone."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GardenIrrigationCoordinator, ZoneSnapshot
from .model.recommendation import Message


class GardenIrrigationEntity(CoordinatorEntity[GardenIrrigationCoordinator]):
    """Entity of the installation device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GardenIrrigationCoordinator,
        description: EntityDescription,
    ) -> None:
        """Bind the entity to the installation device."""
        super().__init__(coordinator)
        self.entity_description = description
        entry_id = coordinator.entry.entry_id
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry_id)})


class GardenIrrigationZoneEntity(CoordinatorEntity[GardenIrrigationCoordinator]):
    """Entity of a zone device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GardenIrrigationCoordinator,
        zone_id: str,
        description: EntityDescription,
    ) -> None:
        """Bind the entity to its zone device."""
        super().__init__(coordinator)
        self.entity_description = description
        self.zone_id = zone_id
        self._attr_unique_id = f"{zone_id}_{description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, zone_id)})

    @property
    def snapshot(self) -> ZoneSnapshot:
        """Current data of this entity's zone."""
        return self.coordinator.data.zones[self.zone_id]


def round_or_none(value: float | None, digits: int = 2) -> float | None:
    """Round for attributes, keeping None."""
    return round(value, digits) if value is not None else None


def messages_as_attributes(messages: Iterable[Message]) -> list[dict[str, Any]]:
    """Reason/warning codes with their (rounded) values, for attributes."""
    return [
        {
            "code": str(message.code),
            **{
                key: round(value, 2) if isinstance(value, float) else value
                for key, value in message.params.items()
            },
        }
        for message in messages
    ]
