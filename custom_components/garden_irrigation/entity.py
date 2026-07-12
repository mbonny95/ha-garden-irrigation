"""Shared base entity for garden_irrigation."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GardenIrrigationCoordinator


class GardenIrrigationEntity(CoordinatorEntity[GardenIrrigationCoordinator]):
    """Base entity: single shared device, entity-only names (has_entity_name)."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry
    ) -> None:
        """Bind the entity to the coordinator and the owning config entry."""
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Single logical device: this integration does not control hardware."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Garden Irrigation",
            manufacturer="garden_irrigation",
            model="Irrigation decision support",
            entry_type=DeviceEntryType.SERVICE,
        )
