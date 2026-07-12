"""Sensor platform for garden_irrigation.

Milestone 1 exposes a single diagnostic sensor, `data_quality`, so the entity
lifecycle (device, unique_id, translations, availability) can be exercised
end-to-end before the real computation engines exist. See const.py for why it
is restricted to exactly two states in this milestone.
"""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_QUALITY_INITIALIZING,
    DATA_QUALITY_NOT_CONFIGURED,
    DATA_QUALITY_STATES,
    DOMAIN,
)
from .coordinator import GardenIrrigationCoordinator
from .entity import GardenIrrigationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the garden_irrigation sensor platform."""
    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DataQualitySensor(coordinator, entry)])


class DataQualitySensor(GardenIrrigationEntity, SensorEntity):
    """Diagnostic sensor reporting overall data-quality status.

    Milestone 1: always available, and its value is one of exactly two
    states — `not_configured` before the coordinator has completed its first
    refresh, `initializing` afterwards. Real stale/battery/signal/weather
    quality logic is added in Milestone 2 without changing this contract.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = DATA_QUALITY_STATES
    _attr_translation_key = "data_quality"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize with a stable unique_id derived from the config entry."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_data_quality"

    @property
    def available(self) -> bool:
        """Always available in Milestone 1 (never unavailable)."""
        return True

    @property
    def native_value(self) -> str:
        """Return `not_configured` pre-refresh, `initializing` afterwards."""
        data = self.coordinator.data
        if not data:
            return DATA_QUALITY_NOT_CONFIGURED
        return str(data.get("data_quality", DATA_QUALITY_INITIALIZING))
