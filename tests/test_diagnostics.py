"""Tests for garden_irrigation config entry diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import (
    CONF_TELEGRAM_CHAT_ID,
    CONF_TELEGRAM_CONFIG_ENTRY_ID,
    DATA_QUALITY_INITIALIZING,
    DOMAIN,
)
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

REDACTED = "**REDACTED**"


def _full_entry_data() -> dict:
    return {
        **user_step_input(),
        **rain_step_input(),
        **soil_step_input(),
        **zones_step_input(),
        CONF_TELEGRAM_CONFIG_ENTRY_ID: "some-telegram-entry-id",
        CONF_TELEGRAM_CHAT_ID: "123456789",
        **telegram_step_input(),
    }


async def test_diagnostics_redacts_telegram_target(hass: HomeAssistant) -> None:
    """Telegram chat_id/config_entry_id must be redacted from diagnostics."""
    setup_mock_weather_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["data"][CONF_TELEGRAM_CHAT_ID] == REDACTED
    assert diagnostics["entry"]["data"][CONF_TELEGRAM_CONFIG_ENTRY_ID] == REDACTED
    # Milestone 3 adds an "et0" key to coordinator.data (see coordinator.py);
    # its own computation is covered by tests/test_et0.py, not re-asserted here.
    assert diagnostics["coordinator_data"]["data_quality"] == DATA_QUALITY_INITIALIZING
    assert "et0" in diagnostics["coordinator_data"]
