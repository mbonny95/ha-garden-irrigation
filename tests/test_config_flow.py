"""Tests for the main config flow (weather sources and site)."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import DOMAIN

from .common import (
    HUMIDITY,
    PRESSURE,
    RAIN,
    TEMPERATURE,
    WEATHER_INPUT,
    WIND,
    set_sensor,
)


async def _start(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result["flow_id"]


@pytest.mark.usefixtures("weather_states")
async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, WEATHER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garden Irrigation"
    assert result["data"] == WEATHER_INPUT


@pytest.mark.usefixtures("weather_states")
async def test_pressure_is_optional(hass: HomeAssistant) -> None:
    flow_id = await _start(hass)
    user_input = {k: v for k, v in WEATHER_INPUT.items() if k != "pressure_entity"}
    result = await hass.config_entries.flow.async_configure(flow_id, user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "pressure_entity" not in result["data"]


@pytest.mark.usefixtures("weather_states")
async def test_other_units_are_accepted(hass: HomeAssistant) -> None:
    set_sensor(hass, TEMPERATURE, "64.8", "°F")
    set_sensor(hass, WIND, "3.8", "mph")
    set_sensor(hass, PRESSURE, "29.9", "inHg")
    set_sensor(hass, RAIN, "0.05", "in", "total")
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, WEATHER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("weather_states")
async def test_unavailable_source_is_accepted(hass: HomeAssistant) -> None:
    set_sensor(hass, HUMIDITY, "unavailable", "%")
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, WEATHER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("entity_id", "state", "unit", "state_class", "field", "error"),
    [
        (TEMPERATURE, "18", "kWh", "measurement", "temperature_entity", "wrong_unit"),
        (TEMPERATURE, "18", None, "measurement", "temperature_entity", "wrong_unit"),
        (HUMIDITY, "71", "%", None, "humidity_entity", "wrong_state_class"),
        (RAIN, "1.2", "mm", "measurement", "rain_entity", "wrong_state_class"),
        (WIND, "calm", "km/h", "measurement", "wind_speed_entity", "not_numeric"),
    ],
)
@pytest.mark.usefixtures("weather_states")
async def test_invalid_sources_show_errors(
    hass: HomeAssistant,
    entity_id: str,
    state: str,
    unit: str | None,
    state_class: str | None,
    field: str,
    error: str,
) -> None:
    set_sensor(hass, entity_id, state, unit, state_class)
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, WEATHER_INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {field: error}


@pytest.mark.usefixtures("weather_states")
async def test_missing_entity(hass: HomeAssistant) -> None:
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**WEATHER_INPUT, "pressure_entity": "sensor.does_not_exist"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"pressure_entity": "entity_not_found"}


async def test_single_instance(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reconfigure_updates_sources(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    set_sensor(hass, "sensor.other_temperature", "17", "°C")

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_input = {**WEATHER_INPUT, "temperature_entity": "sensor.other_temperature"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data["temperature_entity"] == "sensor.other_temperature"


async def test_reconfigure_validates(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**WEATHER_INPUT, "rain_entity": "sensor.nope"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"rain_entity": "entity_not_found"}
