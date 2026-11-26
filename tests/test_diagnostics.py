"""Tests for the diagnostics download."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .common import ZONE_ID


async def test_diagnostics(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await config_entry.runtime_data.coordinator.async_set_deficit(ZONE_ID, 12.0)

    result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert result["entry"]["data"]["latitude"] == "**REDACTED**"
    assert result["entry"]["zones"][ZONE_ID]["title"] == "Small lawn"
    assert result["store"]["zones"][ZONE_ID]["deficit_mm"] == 12.0
    zone = result["data"]["zones"][ZONE_ID]
    assert zone["deficit_mm"] == 12.0
    assert zone["recommendation"]["needs_irrigation"] is True
    assert zone["soil_sensor"] is None
    assert result["data"]["forecast"] is None
