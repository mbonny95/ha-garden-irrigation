"""Test data shared across garden_irrigation tests."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

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


# --- Recorder statistics ------------------------------------------------------------


def import_day_statistics(
    hass: HomeAssistant,
    day: date,
    *,
    rain_mm: float = 0.0,
    hours: int = 24,
    sources: tuple[str, ...] = (TEMPERATURE, HUMIDITY, SOLAR, WIND, RAIN),
) -> None:
    """Import one local day of hourly statistics shaped like FAO-56 Example 18.

    Rain falls in the last hour of the day; the rain counter restarts at 0 at
    the beginning of each day (statistics `sum` keeps growing).
    """
    start = dt_util.start_of_local_day(day)
    slots = [start + timedelta(hours=h) for h in range(hours)]
    rows: dict[str, list[dict[str, Any]]] = {
        TEMPERATURE: [
            {"start": h, "mean": 17.0, "min": 12.3, "max": 21.5} for h in slots
        ],
        HUMIDITY: [{"start": h, "mean": 72.0, "min": 63.0, "max": 84.0} for h in slots],
        SOLAR: [{"start": h, "mean": 255.44, "min": 0.0, "max": 800.0} for h in slots],
        WIND: [{"start": h, "mean": 2.078, "min": 0.0, "max": 6.0} for h in slots],
    }
    units = {
        TEMPERATURE: ("°C", "temperature"),
        HUMIDITY: ("%", None),
        SOLAR: ("W/m²", None),
        WIND: ("m/s", "speed"),
    }
    for entity_id, (unit, unit_class) in units.items():
        if entity_id in sources:
            _import(hass, entity_id, unit, unit_class, rows[entity_id], has_sum=False)
    if RAIN in sources:
        base = _RAIN_SUM.get(hass, 0.0)
        rain_rows = [{"start": start - timedelta(hours=1), "state": base, "sum": base}]
        for index, slot in enumerate(slots):
            total = base + (rain_mm if index == hours - 1 else 0.0)
            rain_rows.append({"start": slot, "state": total, "sum": total})
        _RAIN_SUM[hass] = base + rain_mm
        _import(hass, RAIN, "mm", "distance", rain_rows, has_sum=True)


_RAIN_SUM: dict[HomeAssistant, float] = {}


def _import(
    hass: HomeAssistant,
    entity_id: str,
    unit: str,
    unit_class: str | None,
    rows: list[dict[str, Any]],
    *,
    has_sum: bool,
) -> None:
    async_import_statistics(
        hass,
        {
            "mean_type": (
                StatisticMeanType.NONE if has_sum else StatisticMeanType.ARITHMETIC
            ),
            "has_sum": has_sum,
            "name": None,
            "source": "recorder",
            "statistic_id": entity_id,
            "unit_class": unit_class,
            "unit_of_measurement": unit,
        },
        rows,  # type: ignore[arg-type]
    )


def get_device(
    registry: dr.DeviceRegistry, identifier: tuple[str, str], config_entry_id: str
) -> dr.DeviceEntry | None:
    """Look a device up by identifier on old and new device registries.

    Home Assistant 2026.10 deprecated async_get_device in favour of
    async_get_device_by_identifier (scoped to a config entry).
    """
    lookup = getattr(registry, "async_get_device_by_identifier", None)
    if lookup is not None:
        device: dr.DeviceEntry | None = lookup(identifier, config_entry_id)
        return device
    return registry.async_get_device({identifier})
