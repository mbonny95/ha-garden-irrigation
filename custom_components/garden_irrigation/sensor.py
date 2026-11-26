"""Sensors: installation weather/data quality and per-zone balance.

All millimeters, minutes and liters are estimates of the FAO-56 model.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfPrecipitationDepth, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SOURCE_MAINS, SOURCE_TANK
from .coordinator import CoordinatorData, GardenIrrigationCoordinator, ZoneSnapshot
from .data import GardenIrrigationConfigEntry
from .entity import (
    GardenIrrigationEntity,
    GardenIrrigationZoneEntity,
    messages_as_attributes,
    round_or_none,
)
from .soil_sensor import SoilStatus

MM = UnitOfPrecipitationDepth.MILLIMETERS

DATA_QUALITY_OK = "ok"
DATA_QUALITY_INCOMPLETE = "incomplete"
DATA_QUALITY_WAITING = "waiting"


# --- Installation sensors ---------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class InstallationSensorDescription(SensorEntityDescription):
    """Sensor of the installation device."""

    value_fn: Callable[[CoordinatorData], Any]
    attributes_fn: Callable[[CoordinatorData], Mapping[str, Any]] = lambda _: {}
    requires_forecast: bool = False


def _weather_attributes(data: CoordinatorData) -> dict[str, Any]:
    day = data.weather_day
    if day is None:
        return {}
    return {
        "date": day["date"],
        "method": day["et0_method"],
        "estimate": day["et0_method"] == "hargreaves",
        "missing_inputs": day["missing"],
        "incomplete_sources": day["incomplete"],
    }


def _data_quality(data: CoordinatorData) -> str:
    if data.weather_day is None:
        return DATA_QUALITY_WAITING
    return (
        DATA_QUALITY_INCOMPLETE if data.weather_day["incomplete"] else DATA_QUALITY_OK
    )


def _forecast_attributes(data: CoordinatorData) -> dict[str, Any]:
    forecast = data.forecast
    if forecast is None:
        return {}
    return {
        "entity_id": forecast.entity_id,
        "kind": forecast.kind,
        "fetched_at": forecast.fetched_at.isoformat(),
        "informational_only": True,
    }


INSTALLATION_SENSORS: tuple[InstallationSensorDescription, ...] = (
    InstallationSensorDescription(
        key="et0_yesterday",
        translation_key="et0_yesterday",
        native_unit_of_measurement=MM,
        suggested_display_precision=1,
        value_fn=lambda d: d.weather_day["et0_mm"] if d.weather_day else None,
        attributes_fn=_weather_attributes,
    ),
    InstallationSensorDescription(
        key="rain_yesterday",
        translation_key="rain_yesterday",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=MM,
        suggested_display_precision=1,
        value_fn=lambda d: d.weather_day["rain_mm"] if d.weather_day else None,
        attributes_fn=lambda d: (
            {"date": d.weather_day["date"]} if d.weather_day else {}
        ),
    ),
    InstallationSensorDescription(
        key="data_quality",
        translation_key="data_quality",
        device_class=SensorDeviceClass.ENUM,
        options=[DATA_QUALITY_OK, DATA_QUALITY_INCOMPLETE, DATA_QUALITY_WAITING],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_data_quality,
        attributes_fn=_weather_attributes,
    ),
    InstallationSensorDescription(
        key="forecast_rain",
        translation_key="forecast_rain",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=MM,
        suggested_display_precision=1,
        requires_forecast=True,
        value_fn=lambda d: round_or_none(d.forecast.rain_mm, 1) if d.forecast else None,
        attributes_fn=_forecast_attributes,
    ),
)


class InstallationSensor(GardenIrrigationEntity, SensorEntity):
    """Sensor of the installation device."""

    entity_description: InstallationSensorDescription

    @property
    def native_value(self) -> Any:
        """Value from the coordinator data."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Explanation of the value."""
        return self.entity_description.attributes_fn(self.coordinator.data)


# --- Zone sensors ---------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ZoneSensorDescription(SensorEntityDescription):
    """Sensor of a zone device."""

    value_fn: Callable[[ZoneSnapshot], Any]
    attributes_fn: Callable[[ZoneSnapshot], Mapping[str, Any]] = lambda _: {}
    source: str | None = None  # only created when the zone has this source
    requires_soil_sensor: bool = False


def _deficit_attributes(zone: ZoneSnapshot) -> dict[str, Any]:
    return {
        "closed_deficit_mm": round_or_none(zone.closed_deficit_mm),
        "last_balance_date": (
            zone.last_balance_date.isoformat() if zone.last_balance_date else None
        ),
        "irrigation_since_mm": round(zone.pending_irrigation_mm, 2),
        "taw_mm": round(zone.soil.taw_mm, 2),
        "raw_mm": round(zone.soil.raw_mm, 2),
    }


def _recommendation_attributes(zone: ZoneSnapshot) -> dict[str, Any]:
    rec = zone.recommendation
    return {
        "estimate": True,
        "liters": round(rec.liters),
        "blocks_mm": [round(block, 2) for block in rec.blocks_mm],
        "block_pause_min": rec.block_pause_min,
        "reasons": messages_as_attributes(rec.reasons),
        "warnings": messages_as_attributes(rec.warnings),
    }


def _minutes(source: str) -> Callable[[ZoneSnapshot], float | None]:
    def value(zone: ZoneSnapshot) -> float | None:
        plan = zone.recommendation.sources.get(source)
        return round(plan.total_minutes, 1) if plan else None

    return value


def _minutes_attributes(source: str) -> Callable[[ZoneSnapshot], dict[str, Any]]:
    def attributes(zone: ZoneSnapshot) -> dict[str, Any]:
        plan = zone.recommendation.sources.get(source)
        return {
            "estimate": True,
            "block_minutes": (
                [round(minutes, 1) for minutes in plan.block_minutes] if plan else []
            ),
            "block_pause_min": zone.recommendation.block_pause_min,
            "rate_mm_per_min": zone.config.source_rates.get(source),
        }

    return attributes


def _last_day(key: str) -> Callable[[ZoneSnapshot], float | None]:
    def value(zone: ZoneSnapshot) -> float | None:
        if zone.last_day is None:
            return None
        result = zone.last_day.get(key)
        return float(result) if isinstance(result, int | float) else None

    return value


def _last_day_attributes(zone: ZoneSnapshot) -> dict[str, Any]:
    if zone.last_day is None:
        return {}
    return {
        "date": zone.last_day["date"],
        "incomplete_sources": zone.last_day["incomplete"],
    }


def _soil_status(zone: ZoneSnapshot) -> str | None:
    return zone.soil_sensor.status.value if zone.soil_sensor else None


def _soil_attributes(zone: ZoneSnapshot) -> dict[str, Any]:
    sensor = zone.soil_sensor
    if sensor is None:
        return {}
    return {
        "entity_id": sensor.entity_id,
        "value_pct": sensor.value_pct,
        "dry_pct": sensor.dry_pct,
        "wet_pct": sensor.wet_pct,
        "last_reported": (
            sensor.last_reported.isoformat() if sensor.last_reported else None
        ),
        "device_relative": True,
    }


ZONE_SENSORS: tuple[ZoneSensorDescription, ...] = (
    ZoneSensorDescription(
        key="deficit",
        translation_key="deficit",
        native_unit_of_measurement=MM,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda z: round_or_none(z.deficit_mm),
        attributes_fn=_deficit_attributes,
    ),
    ZoneSensorDescription(
        key="recommended_irrigation",
        translation_key="recommended_irrigation",
        native_unit_of_measurement=MM,
        suggested_display_precision=1,
        value_fn=lambda z: (
            round(z.recommendation.amount_mm, 2)
            if z.recommendation.needs_irrigation is not None
            else None
        ),
        attributes_fn=_recommendation_attributes,
    ),
    ZoneSensorDescription(
        key="recommended_minutes_mains",
        translation_key="recommended_minutes_mains",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        source=SOURCE_MAINS,
        value_fn=_minutes(SOURCE_MAINS),
        attributes_fn=_minutes_attributes(SOURCE_MAINS),
    ),
    ZoneSensorDescription(
        key="recommended_minutes_tank",
        translation_key="recommended_minutes_tank",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        source=SOURCE_TANK,
        value_fn=_minutes(SOURCE_TANK),
        attributes_fn=_minutes_attributes(SOURCE_TANK),
    ),
    ZoneSensorDescription(
        key="irrigation_7d",
        translation_key="irrigation_7d",
        native_unit_of_measurement=MM,
        suggested_display_precision=1,
        value_fn=lambda z: round(z.irrigation_7d_mm, 2),
    ),
    ZoneSensorDescription(
        key="last_irrigation",
        translation_key="last_irrigation",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda z: z.last_irrigation,
    ),
    ZoneSensorDescription(
        key="taw",
        translation_key="taw",
        native_unit_of_measurement=MM,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda z: round(z.soil.taw_mm, 2),
    ),
    ZoneSensorDescription(
        key="raw",
        translation_key="raw",
        native_unit_of_measurement=MM,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda z: round(z.soil.raw_mm, 2),
    ),
    ZoneSensorDescription(
        key="kc",
        translation_key="kc",
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda z: z.kc_today,
    ),
    ZoneSensorDescription(
        key="etc_yesterday",
        translation_key="etc_yesterday",
        native_unit_of_measurement=MM,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_last_day("etc_mm"),
        attributes_fn=_last_day_attributes,
    ),
    ZoneSensorDescription(
        key="effective_rain_yesterday",
        translation_key="effective_rain_yesterday",
        native_unit_of_measurement=MM,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_last_day("effective_rain_mm"),
        attributes_fn=_last_day_attributes,
    ),
    ZoneSensorDescription(
        key="soil_moisture_status",
        translation_key="soil_moisture_status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.value for status in SoilStatus],
        entity_category=EntityCategory.DIAGNOSTIC,
        requires_soil_sensor=True,
        value_fn=_soil_status,
        attributes_fn=_soil_attributes,
    ),
)


class ZoneSensor(GardenIrrigationZoneEntity, SensorEntity):
    """Sensor of a zone device."""

    entity_description: ZoneSensorDescription

    @property
    def native_value(self) -> float | datetime | None:
        """Value from the zone snapshot."""
        value: float | datetime | None = self.entity_description.value_fn(self.snapshot)
        return value

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Explanation of the value."""
        return self.entity_description.attributes_fn(self.snapshot)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GardenIrrigationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the installation sensors and the sensors of every zone."""
    coordinator: GardenIrrigationCoordinator = entry.runtime_data.coordinator
    async_add_entities(
        InstallationSensor(coordinator, description)
        for description in INSTALLATION_SENSORS
        if not description.requires_forecast or coordinator.options.forecast_entity
    )
    for zone_id, zone in coordinator.zones.items():
        async_add_entities(
            (
                ZoneSensor(coordinator, zone_id, description)
                for description in ZONE_SENSORS
                if (
                    description.source is None
                    or description.source in zone.source_rates
                )
                and (not description.requires_soil_sensor or zone.soil_moisture_entity)
            ),
            config_subentry_id=zone_id,
        )
