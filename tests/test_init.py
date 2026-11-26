"""Tests for entry setup, unload, reload and removal."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import DOMAIN

from .common import ZONE_ID

STORE_KEY_PREFIX = f"{DOMAIN}."


def _stored_zone(deficit: float) -> dict[str, Any]:
    return {
        "deficit_mm": deficit,
        "last_balance_date": None,
        "days": [],
        "irrigations": [],
    }


async def test_setup_and_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_prunes_state_of_removed_zones(
    hass: HomeAssistant, config_entry: MockConfigEntry, hass_storage: dict[str, Any]
) -> None:
    hass_storage[STORE_KEY_PREFIX + config_entry.entry_id] = {
        "version": 1,
        "minor_version": 1,
        "key": STORE_KEY_PREFIX + config_entry.entry_id,
        "data": {"zones": {ZONE_ID: _stored_zone(4.0), "gone": _stored_zone(9.0)}},
    }

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    store = config_entry.runtime_data.store
    assert store.zone_ids() == [ZONE_ID]
    assert store.zone(ZONE_ID)["deficit_mm"] == 4.0


async def test_options_change_reloads_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    first_runtime = config_entry.runtime_data

    hass.config_entries.async_update_entry(
        config_entry, options={"rain_threshold_mm": 3.0}
    )
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not first_runtime


async def test_unload_flushes_store(
    hass: HomeAssistant, config_entry: MockConfigEntry, hass_storage: dict[str, Any]
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    config_entry.runtime_data.store.zone(ZONE_ID)["deficit_mm"] = 6.5

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    saved = hass_storage[STORE_KEY_PREFIX + config_entry.entry_id]["data"]
    assert saved["zones"][ZONE_ID]["deficit_mm"] == 6.5


async def test_remove_entry_deletes_store(
    hass: HomeAssistant, config_entry: MockConfigEntry, hass_storage: dict[str, Any]
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(config_entry.entry_id)
    assert STORE_KEY_PREFIX + config_entry.entry_id in hass_storage

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    assert STORE_KEY_PREFIX + config_entry.entry_id not in hass_storage


async def test_v1_entry_is_not_loaded(
    hass: HomeAssistant, weather_states: None
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, version=1, data={"altitude": 116})
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
