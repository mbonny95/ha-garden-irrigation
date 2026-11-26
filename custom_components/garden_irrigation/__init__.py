"""Garden Irrigation: FAO-56 irrigation decision support for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import GardenIrrigationCoordinator
from .data import GardenIrrigationConfigEntry, GardenIrrigationRuntimeData
from .repairs import async_clear_issues
from .services import async_setup_services
from .store import GardenIrrigationStore

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

MAIN_DEVICE_NAME = "Garden Irrigation"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration's actions."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: GardenIrrigationConfigEntry
) -> bool:
    """Set up the integration from its config entry."""
    store = GardenIrrigationStore(hass, entry.entry_id)
    await store.async_load()
    zones_pruned = store.prune_zones(entry.subentries)
    history_pruned = store.prune_history(dt_util.now().date())
    if zones_pruned or history_pruned:
        store.async_schedule_save()

    coordinator = GardenIrrigationCoordinator(hass, entry, store)
    _async_register_devices(hass, entry, coordinator)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = GardenIrrigationRuntimeData(
        store=store, coordinator=coordinator
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    for unsubscribe in coordinator.async_start():
        entry.async_on_unload(unsubscribe)
    # Options and zone (subentry) changes both go through an entry update:
    # reload so every zone's entities and the daily job pick them up.
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GardenIrrigationConfigEntry
) -> bool:
    """Unload the config entry, flushing pending writes."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.store.async_save()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete persisted data when the integration is removed."""
    await GardenIrrigationStore(hass, entry.entry_id).async_remove()
    async_clear_issues(hass)


async def _async_reload_on_update(
    hass: HomeAssistant, entry: GardenIrrigationConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_devices(
    hass: HomeAssistant,
    entry: GardenIrrigationConfigEntry,
    coordinator: GardenIrrigationCoordinator,
) -> None:
    """One device for the installation, one per zone (actions target zones)."""
    registry = dr.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=MAIN_DEVICE_NAME,
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    for zone_id, zone in coordinator.zones.items():
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            config_subentry_id=zone_id,
            identifiers={(DOMAIN, zone_id)},
            name=zone.name,
            entry_type=dr.DeviceEntryType.SERVICE,
            via_device=(DOMAIN, entry.entry_id),
        )
