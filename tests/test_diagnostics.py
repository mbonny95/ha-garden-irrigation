"""Tests for garden_irrigation config entry diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import DATA_QUALITY_INITIALIZING, DOMAIN
from custom_components.garden_irrigation.diagnostics import (
    async_get_config_entry_diagnostics,
)

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


async def test_diagnostics_reports_coordinator_data(hass: HomeAssistant) -> None:
    setup_mock_weather_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    # Milestone 3 adds an "et0" key to coordinator.data (see coordinator.py);
    # its own computation is covered by tests/test_et0.py, not re-asserted here.
    assert diagnostics["coordinator_data"]["data_quality"] == DATA_QUALITY_INITIALIZING
    assert "et0" in diagnostics["coordinator_data"]
