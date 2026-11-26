"""Garden Irrigation: FAO-56 irrigation decision support for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .data import GardenIrrigationConfigEntry, GardenIrrigationRuntimeData
from .store import GardenIrrigationStore

PLATFORMS: list[Platform] = []


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

    entry.runtime_data = GardenIrrigationRuntimeData(store=store)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
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


async def _async_reload_on_update(
    hass: HomeAssistant, entry: GardenIrrigationConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
