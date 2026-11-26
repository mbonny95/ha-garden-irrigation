"""Typed views of the config entry: site, operating options and zones."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import time
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_NAME

from .const import (
    CONF_ADJUST_P_FOR_ETC,
    CONF_ANEMOMETER_HEIGHT,
    CONF_AREA,
    CONF_AWC,
    CONF_BLOCK_PAUSE,
    CONF_CROP_PROFILE,
    CONF_DEPLETION_FRACTION,
    CONF_FORECAST_ENTITY,
    CONF_HARGREAVES_FALLBACK,
    CONF_KC_MONTHLY,
    CONF_MAX_BLOCK,
    CONF_MIN_INTERVAL_HOURS,
    CONF_RAIN_FACTOR,
    CONF_RAIN_THRESHOLD,
    CONF_ROOT_DEPTH,
    CONF_RUN_TIME,
    CONF_SOIL_MOISTURE_DRY,
    CONF_SOIL_MOISTURE_ENTITY,
    CONF_SOIL_MOISTURE_WET,
    CONF_SOIL_TYPE,
    CONF_WEEKLY_CAP,
    DEFAULT_ADJUST_P_FOR_ETC,
    DEFAULT_ANEMOMETER_HEIGHT_M,
    DEFAULT_BLOCK_PAUSE_MINUTES,
    DEFAULT_HARGREAVES_FALLBACK,
    DEFAULT_MIN_INTERVAL_HOURS,
    DEFAULT_RAIN_FACTOR,
    DEFAULT_RAIN_THRESHOLD_MM,
    DEFAULT_RUN_TIME,
    SOURCE_RATE_KEYS,
    SUBENTRY_TYPE_ZONE,
)
from .daily_weather import SOURCE_FIELDS
from .model.crops import (
    CROP_CUSTOM,
    DEFAULT_CROP,
    DEFAULT_DEPLETION_FRACTION,
    DEFAULT_ROOT_DEPTH_MM,
    KC_PROFILES,
)
from .model.fao56 import Site
from .model.soils import DEFAULT_SOIL, SOILS


def site_from_entry(entry: ConfigEntry) -> Site:
    """FAO-56 site parameters of the installation."""
    return Site(
        latitude_deg=float(entry.data[CONF_LATITUDE]),
        elevation_m=float(entry.data[CONF_ELEVATION]),
        anemometer_height_m=float(
            entry.data.get(CONF_ANEMOMETER_HEIGHT, DEFAULT_ANEMOMETER_HEIGHT_M)
        ),
    )


def weather_sources(entry: ConfigEntry) -> dict[str, str]:
    """Configured weather source fields mapped to their entity ids."""
    return {
        field: entry.data[field] for field in SOURCE_FIELDS if entry.data.get(field)
    }


@dataclass(frozen=True, slots=True)
class OperatingOptions:
    """Operational parameters from the options flow, with defaults."""

    rain_factor: float
    rain_threshold_mm: float
    run_time: time
    hargreaves_fallback: bool
    adjust_p_for_etc: bool
    forecast_entity: str | None
    min_interval_h: float
    weekly_cap_mm: float | None
    block_pause_min: float

    @classmethod
    def from_entry(cls, entry: ConfigEntry) -> OperatingOptions:
        """Read the entry options, filling in defaults."""
        options: Mapping[str, Any] = entry.options
        cap = options.get(CONF_WEEKLY_CAP)
        return cls(
            rain_factor=float(options.get(CONF_RAIN_FACTOR, DEFAULT_RAIN_FACTOR)),
            rain_threshold_mm=float(
                options.get(CONF_RAIN_THRESHOLD, DEFAULT_RAIN_THRESHOLD_MM)
            ),
            run_time=time.fromisoformat(options.get(CONF_RUN_TIME, DEFAULT_RUN_TIME)),
            hargreaves_fallback=bool(
                options.get(CONF_HARGREAVES_FALLBACK, DEFAULT_HARGREAVES_FALLBACK)
            ),
            adjust_p_for_etc=bool(
                options.get(CONF_ADJUST_P_FOR_ETC, DEFAULT_ADJUST_P_FOR_ETC)
            ),
            forecast_entity=options.get(CONF_FORECAST_ENTITY) or None,
            min_interval_h=float(
                options.get(CONF_MIN_INTERVAL_HOURS, DEFAULT_MIN_INTERVAL_HOURS)
            ),
            weekly_cap_mm=float(cap) if cap is not None else None,
            block_pause_min=float(
                options.get(CONF_BLOCK_PAUSE, DEFAULT_BLOCK_PAUSE_MINUTES)
            ),
        )


@dataclass(frozen=True, slots=True)
class ZoneConfig:
    """One irrigated zone, with presets resolved."""

    zone_id: str
    name: str
    area_m2: float
    kc_monthly: tuple[float, ...]
    awc_mm_per_m: float
    max_block_mm: float
    root_depth_mm: float
    depletion_fraction: float
    source_rates: dict[str, float]  # only sources with a measured rate
    soil_moisture_entity: str | None
    soil_moisture_dry: float | None
    soil_moisture_wet: float | None

    @classmethod
    def from_subentry(cls, subentry: ConfigSubentry) -> ZoneConfig:
        """Build a zone from its subentry data."""
        data = subentry.data
        profile = data.get(CONF_CROP_PROFILE, DEFAULT_CROP)
        kc = (
            data[CONF_KC_MONTHLY]
            if profile == CROP_CUSTOM
            else KC_PROFILES.get(profile, KC_PROFILES[DEFAULT_CROP])
        )
        soil = SOILS.get(data.get(CONF_SOIL_TYPE, DEFAULT_SOIL), SOILS[DEFAULT_SOIL])
        awc = data.get(CONF_AWC)
        max_block = data.get(CONF_MAX_BLOCK)
        return cls(
            zone_id=subentry.subentry_id,
            name=str(data.get(CONF_NAME, subentry.title)),
            area_m2=float(data[CONF_AREA]),
            kc_monthly=tuple(float(value) for value in kc),
            awc_mm_per_m=float(awc) if awc is not None else soil.awc_mm_per_m,
            max_block_mm=float(max_block)
            if max_block is not None
            else soil.max_block_mm,
            root_depth_mm=float(data.get(CONF_ROOT_DEPTH, DEFAULT_ROOT_DEPTH_MM)),
            depletion_fraction=float(
                data.get(CONF_DEPLETION_FRACTION, DEFAULT_DEPLETION_FRACTION)
            ),
            source_rates={
                source: float(data[key])
                for source, key in SOURCE_RATE_KEYS.items()
                if data.get(key) is not None
            },
            soil_moisture_entity=data.get(CONF_SOIL_MOISTURE_ENTITY) or None,
            soil_moisture_dry=_optional_float(data.get(CONF_SOIL_MOISTURE_DRY)),
            soil_moisture_wet=_optional_float(data.get(CONF_SOIL_MOISTURE_WET)),
        )


def zones_from_entry(entry: ConfigEntry) -> dict[str, ZoneConfig]:
    """All zones of the entry, keyed by subentry id."""
    return {
        subentry_id: ZoneConfig.from_subentry(subentry)
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_ZONE
    }


def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None
