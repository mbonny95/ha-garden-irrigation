"""Test data shared across garden_irrigation tests."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

TEMPERATURE = "sensor.outdoor_temperature"
HUMIDITY = "sensor.outdoor_humidity"
SOLAR = "sensor.solar_radiation"
WIND = "sensor.wind_speed"
RAIN = "sensor.daily_rain"
PRESSURE = "sensor.pressure"
SOIL = "sensor.soil_moisture_1"

ZONE_ID = "zone_small"

WEATHER_INPUT: dict[str, Any] = {
    "temperature_entity": TEMPERATURE,
    "humidity_entity": HUMIDITY,
    "solar_radiation_entity": SOLAR,
    "wind_speed_entity": WIND,
    "rain_entity": RAIN,
    "pressure_entity": PRESSURE,
    "anemometer_height_m": 2.0,
    "latitude": 45.5,
    "elevation": 116,
}

ZONE_INPUT: dict[str, Any] = {
    "name": "Small lawn",
    "area_m2": 38.0,
    "crop_profile": "cool_season_turf",
    "soil_type": "loam",
    "root_depth_mm": 150.0,
    "depletion_fraction": 0.4,
    "rate_mains_mm_per_min": 0.25,
}


def set_sensor(
    hass: HomeAssistant,
    entity_id: str,
    state: str,
    unit: str | None,
    state_class: str | None = "measurement",
) -> None:
    """Write a sensor state with the given unit and state class."""
    attributes: dict[str, Any] = {}
    if unit is not None:
        attributes["unit_of_measurement"] = unit
    if state_class is not None:
        attributes["state_class"] = state_class
    hass.states.async_set(entity_id, state, attributes)


def set_weather_states(hass: HomeAssistant) -> None:
    """Create a valid set of weather source sensors."""
    set_sensor(hass, TEMPERATURE, "18.2", "°C")
    set_sensor(hass, HUMIDITY, "71", "%")
    set_sensor(hass, SOLAR, "240.5", "W/m²")
    set_sensor(hass, WIND, "6.1", "km/h")
    set_sensor(hass, RAIN, "1.2", "mm", "total_increasing")
    set_sensor(hass, PRESSURE, "1012.4", "hPa")
    set_sensor(hass, SOIL, "48", "%", None)
