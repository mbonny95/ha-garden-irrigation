"""Shared mock entity ids and step-input builders for garden_irrigation tests."""

from __future__ import annotations

from typing import Any

from homeassistant.const import (
    PERCENTAGE,
    UnitOfIrradiance,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant

from custom_components.garden_irrigation.const import (
    CONF_ALTITUDE,
    CONF_ANEMOMETER_HEIGHT,
    CONF_DAILY_RAINFALL_ENTITY,
    CONF_HUMIDITY_ENTITY,
    CONF_PRESSURE_ENTITY,
    CONF_RAIN_RATE_ENTITY,
    CONF_SOLAR_RADIATION_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    CONF_WIND_SPEED_ENTITY,
    CONF_ZONE1_AREA_M2,
    CONF_ZONE1_MM_PER_MIN_MAINS,
    CONF_ZONE1_NAME,
    CONF_ZONE1_SOIL_MOISTURE_ENTITY,
    CONF_ZONE2_AREA_M2,
    CONF_ZONE2_MM_PER_MIN_MAINS,
    CONF_ZONE2_NAME,
    CONF_ZONE2_SOIL_MOISTURE_ENTITY,
)

# Mock entity ids. These are test fixtures only — the integration itself never
# hardcodes Ecowitt/WH51 entity names.
MOCK_TEMPERATURE_ENTITY = "sensor.mock_outdoor_temperature"
MOCK_HUMIDITY_ENTITY = "sensor.mock_outdoor_humidity"
MOCK_PRESSURE_ENTITY = "sensor.mock_absolute_pressure"
MOCK_SOLAR_RADIATION_ENTITY = "sensor.mock_solar_irradiance"
MOCK_WIND_SPEED_ENTITY = "sensor.mock_wind_speed"
MOCK_WIND_GUST_ENTITY = "sensor.mock_wind_gust"

MOCK_DAILY_RAINFALL_ENTITY = "sensor.mock_daily_rainfall"
MOCK_RAIN_RATE_ENTITY = "sensor.mock_rain_rate"
MOCK_RAIN_24H_ENTITY = "sensor.mock_rain_24h"
MOCK_RAIN_EVENT_ENTITY = "sensor.mock_rain_event"

MOCK_ZONE1_SOIL_ENTITY = "sensor.mock_soil_ch1"
MOCK_ZONE1_BATTERY_ENTITY = "sensor.mock_soil_battery_ch1"
MOCK_ZONE1_SIGNAL_ENTITY = "sensor.mock_soil_signal_ch1"
MOCK_ZONE2_SOIL_ENTITY = "sensor.mock_soil_ch2"
MOCK_ZONE2_BATTERY_ENTITY = "sensor.mock_soil_battery_ch2"
MOCK_ZONE2_SIGNAL_ENTITY = "sensor.mock_soil_signal_ch2"


def setup_mock_weather_states(hass: HomeAssistant) -> None:
    """Register mock states for every entity a full config flow run needs."""
    hass.states.async_set(
        MOCK_TEMPERATURE_ENTITY,
        "18.5",
        {"unit_of_measurement": UnitOfTemperature.CELSIUS},
    )
    hass.states.async_set(
        MOCK_HUMIDITY_ENTITY, "62", {"unit_of_measurement": PERCENTAGE}
    )
    hass.states.async_set(
        MOCK_PRESSURE_ENTITY,
        "1013.2",
        {"unit_of_measurement": UnitOfPressure.HPA},
    )
    hass.states.async_set(
        MOCK_SOLAR_RADIATION_ENTITY,
        "450",
        {"unit_of_measurement": UnitOfIrradiance.WATTS_PER_SQUARE_METER},
    )
    hass.states.async_set(
        MOCK_WIND_SPEED_ENTITY,
        "8.5",
        {"unit_of_measurement": UnitOfSpeed.KILOMETERS_PER_HOUR},
    )
    hass.states.async_set(
        MOCK_WIND_GUST_ENTITY,
        "14.0",
        {"unit_of_measurement": UnitOfSpeed.KILOMETERS_PER_HOUR},
    )
    hass.states.async_set(
        MOCK_DAILY_RAINFALL_ENTITY,
        "0.0",
        {"unit_of_measurement": UnitOfPrecipitationDepth.MILLIMETERS},
    )
    hass.states.async_set(
        MOCK_RAIN_RATE_ENTITY,
        "0.0",
        {"unit_of_measurement": UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR},
    )
    hass.states.async_set(
        MOCK_RAIN_24H_ENTITY,
        "0.0",
        {"unit_of_measurement": UnitOfPrecipitationDepth.MILLIMETERS},
    )
    hass.states.async_set(
        MOCK_RAIN_EVENT_ENTITY,
        "0.0",
        {"unit_of_measurement": UnitOfPrecipitationDepth.MILLIMETERS},
    )
    hass.states.async_set(
        MOCK_ZONE1_SOIL_ENTITY, "45", {"unit_of_measurement": PERCENTAGE}
    )
    hass.states.async_set(
        MOCK_ZONE1_BATTERY_ENTITY, "100", {"unit_of_measurement": PERCENTAGE}
    )
    hass.states.async_set(MOCK_ZONE1_SIGNAL_ENTITY, "4", {})
    hass.states.async_set(
        MOCK_ZONE2_SOIL_ENTITY, "50", {"unit_of_measurement": PERCENTAGE}
    )
    hass.states.async_set(
        MOCK_ZONE2_BATTERY_ENTITY, "95", {"unit_of_measurement": PERCENTAGE}
    )
    hass.states.async_set(MOCK_ZONE2_SIGNAL_ENTITY, "4", {})


def user_step_input(**overrides: Any) -> dict[str, Any]:
    """Valid input for config-flow step (a): position + FAO-56 weather."""
    data = {
        CONF_ALTITUDE: 116,
        CONF_ANEMOMETER_HEIGHT: 2.0,
        CONF_TEMPERATURE_ENTITY: MOCK_TEMPERATURE_ENTITY,
        CONF_HUMIDITY_ENTITY: MOCK_HUMIDITY_ENTITY,
        CONF_PRESSURE_ENTITY: MOCK_PRESSURE_ENTITY,
        CONF_SOLAR_RADIATION_ENTITY: MOCK_SOLAR_RADIATION_ENTITY,
        CONF_WIND_SPEED_ENTITY: MOCK_WIND_SPEED_ENTITY,
    }
    data.update(overrides)
    return data


def rain_step_input(**overrides: Any) -> dict[str, Any]:
    """Valid input for config-flow step (b): rain."""
    data = {
        CONF_DAILY_RAINFALL_ENTITY: MOCK_DAILY_RAINFALL_ENTITY,
        CONF_RAIN_RATE_ENTITY: MOCK_RAIN_RATE_ENTITY,
    }
    data.update(overrides)
    return data


def soil_step_input(**overrides: Any) -> dict[str, Any]:
    """Valid input for config-flow step (c): WH51 per zone."""
    data = {
        CONF_ZONE1_SOIL_MOISTURE_ENTITY: MOCK_ZONE1_SOIL_ENTITY,
        CONF_ZONE2_SOIL_MOISTURE_ENTITY: MOCK_ZONE2_SOIL_ENTITY,
    }
    data.update(overrides)
    return data


def zones_step_input(**overrides: Any) -> dict[str, Any]:
    """Valid input for config-flow step (d): zone names/areas/distribution."""
    data = {
        CONF_ZONE1_NAME: "Zona 1",
        CONF_ZONE1_AREA_M2: 38,
        CONF_ZONE1_MM_PER_MIN_MAINS: 0.25,
        CONF_ZONE2_NAME: "Zona 2",
        CONF_ZONE2_AREA_M2: 72,
        CONF_ZONE2_MM_PER_MIN_MAINS: 0.175,
    }
    data.update(overrides)
    return data


def telegram_step_input(**overrides: Any) -> dict[str, Any]:
    """Valid (empty/skippable) input for config-flow step (e): Telegram."""
    data: dict[str, Any] = {}
    data.update(overrides)
    return data
