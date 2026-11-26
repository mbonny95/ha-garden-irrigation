"""Tests for the options flow."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

OPTIONS = {
    "rain_effective_factor": 0.75,
    "rain_threshold_mm": 3.0,
    "daily_run_time": "06:00:00",
    "hargreaves_fallback": True,
    "adjust_p_for_etc": False,
    "min_interval_hours": 72,
    "weekly_cap_mm": 40,
    "block_pause_minutes": 45,
}


async def test_options_defaults_and_save(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    defaults = {
        str(key): key.default()
        for key in result["data_schema"].schema
        if key.default is not vol.UNDEFINED
    }
    assert "weekly_cap_mm" not in defaults
    assert "forecast_entity" not in defaults
    assert defaults["rain_effective_factor"] == 0.8
    assert defaults["rain_threshold_mm"] == 2.0
    assert defaults["daily_run_time"] == "05:30:00"
    assert defaults["block_pause_minutes"] == 30

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], OPTIONS
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == OPTIONS


async def test_weekly_cap_can_be_disabled(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    options = {k: v for k, v in OPTIONS.items() if k != "weekly_cap_mm"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], options
    )
    await hass.async_block_till_done()

    assert "weekly_cap_mm" not in config_entry.options
