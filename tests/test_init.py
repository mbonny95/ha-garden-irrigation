"""Tests for garden_irrigation entry setup/unload/reload."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import DOMAIN

from .const import (
    rain_step_input,
    setup_mock_weather_states,
    soil_step_input,
    telegram_step_input,
    user_step_input,
    zones_step_input,
)


def _full_entry_data() -> dict:
    return {
        **user_step_input(),
        **rain_step_input(),
        **soil_step_input(),
        **zones_step_input(),
        **telegram_step_input(),
    }


async def test_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """The entry loads cleanly and creates/removes its coordinator on unload."""
    setup_mock_weather_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.entry_id in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]


async def test_reload_entry(hass: HomeAssistant) -> None:
    """Reloading the entry (e.g. after an options change) succeeds cleanly."""
    setup_mock_weather_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.entry_id in hass.data[DOMAIN]
