"""Tests for the garden_irrigation multi-step config flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import (
    CONF_HUMIDITY_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    DOMAIN,
    STEP_RAIN,
    STEP_SOIL,
    STEP_TELEGRAM,
    STEP_WEATHER,
    STEP_ZONES,
)

from .const import (
    MOCK_ZONE1_SOIL_ENTITY,
    rain_step_input,
    setup_mock_weather_states,
    soil_step_input,
    telegram_step_input,
    user_step_input,
    zones_step_input,
)


async def _advance_to_create_entry(hass: HomeAssistant) -> dict:
    """Run all five steps with valid input and return the final flow result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_WEATHER

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_step_input()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_RAIN

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], rain_step_input()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_SOIL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], soil_step_input()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_ZONES

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], zones_step_input()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_TELEGRAM

    return await hass.config_entries.flow.async_configure(
        result["flow_id"], telegram_step_input()
    )


async def test_happy_path_creates_entry(hass: HomeAssistant) -> None:
    """All five steps, valid input, optional fields omitted -> entry created."""
    setup_mock_weather_states(hass)

    result = await _advance_to_create_entry(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garden Irrigation"
    assert result["data"][CONF_TEMPERATURE_ENTITY]
    assert result["data"]["zone1_soil_moisture_entity"] == MOCK_ZONE1_SOIL_ENTITY
    # Optional fields left empty in the flow must not be required to finish.
    assert "wind_gust_entity" not in result["data"]
    assert "zone1_battery_entity" not in result["data"]
    assert "telegram_entity_id" not in result["data"]


async def test_entity_not_found_blocks_step(hass: HomeAssistant) -> None:
    """A nonexistent entity_id must be rejected with entity_not_found."""
    setup_mock_weather_states(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_step_input(**{CONF_TEMPERATURE_ENTITY: "sensor.does_not_exist_at_all"}),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_WEATHER
    assert result["errors"][CONF_TEMPERATURE_ENTITY] == "entity_not_found"


async def test_entity_wrong_domain_blocks_step(hass: HomeAssistant) -> None:
    """A non-sensor entity_id must be rejected with entity_wrong_domain."""
    setup_mock_weather_states(hass)
    hass.states.async_set("light.mock_light", "on")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_step_input(**{CONF_TEMPERATURE_ENTITY: "light.mock_light"}),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_WEATHER
    assert result["errors"][CONF_TEMPERATURE_ENTITY] == "entity_wrong_domain"


async def test_entity_wrong_unit_blocks_step(hass: HomeAssistant) -> None:
    """An incompatible unit_of_measurement must be rejected."""
    setup_mock_weather_states(hass)
    hass.states.async_set(
        "sensor.mock_humidity_wrong_unit",
        "62",
        {"unit_of_measurement": UnitOfTemperature.CELSIUS},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_step_input(**{CONF_HUMIDITY_ENTITY: "sensor.mock_humidity_wrong_unit"}),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_WEATHER
    assert result["errors"][CONF_HUMIDITY_ENTITY] == "entity_wrong_unit"


async def test_optional_entities_can_be_omitted(hass: HomeAssistant) -> None:
    """Battery/signal/wind_gust are optional: omitting them is not an error."""
    setup_mock_weather_states(hass)

    result = await _advance_to_create_entry(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_instance_is_aborted(hass: HomeAssistant) -> None:
    """single_config_entry: a second flow must abort, not create a 2nd entry."""
    MockConfigEntry(domain=DOMAIN, data={}).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_is_pass_through(hass: HomeAssistant) -> None:
    """Milestone 1 options flow stub: opens and saves with no required fields."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
