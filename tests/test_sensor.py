"""Tests for the garden_irrigation data_quality diagnostic sensor."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import (
    DATA_QUALITY_INITIALIZING,
    DATA_QUALITY_NOT_CONFIGURED,
    DOMAIN,
)
from custom_components.garden_irrigation.coordinator import (
    GardenIrrigationCoordinator,
)
from custom_components.garden_irrigation.sensor import DataQualitySensor

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


async def test_not_configured_before_first_refresh(hass: HomeAssistant) -> None:
    """Before any coordinator refresh, the sensor reports not_configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)
    sensor = DataQualitySensor(coordinator, entry)

    assert sensor.available is True
    assert sensor.native_value == DATA_QUALITY_NOT_CONFIGURED


async def test_initializing_after_first_refresh(hass: HomeAssistant) -> None:
    """After the coordinator's first (skeleton) refresh, state is initializing.

    Uses async_refresh() (a plain manual refresh) rather than
    async_config_entry_first_refresh(), which requires the config entry to be
    in SETUP_IN_PROGRESS state and is exercised end-to-end by
    test_sensor_always_available_via_full_setup below.
    """
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)
    await coordinator.async_refresh()
    sensor = DataQualitySensor(coordinator, entry)

    assert sensor.available is True
    assert sensor.native_value == DATA_QUALITY_INITIALIZING


async def test_sensor_always_available_via_full_setup(hass: HomeAssistant) -> None:
    """End-to-end: after entry setup the entity exists, is available, and
    reports initializing (never unavailable)."""
    setup_mock_weather_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_data_quality"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == DATA_QUALITY_INITIALIZING
    assert state.state != "unavailable"
