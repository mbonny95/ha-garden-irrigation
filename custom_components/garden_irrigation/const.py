"""Constants shared across the garden_irrigation integration.

Agronomic reference data (soils, crop coefficients) lives in `model/`; this
module only holds Home Assistant-facing keys and operational defaults.
"""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "garden_irrigation"

SUBENTRY_TYPE_ZONE: Final = "zone"

# --- Main entry: weather sources and site --------------------------------
CONF_TEMPERATURE_ENTITY: Final = "temperature_entity"
CONF_HUMIDITY_ENTITY: Final = "humidity_entity"
CONF_SOLAR_RADIATION_ENTITY: Final = "solar_radiation_entity"
CONF_WIND_SPEED_ENTITY: Final = "wind_speed_entity"
CONF_RAIN_ENTITY: Final = "rain_entity"
CONF_PRESSURE_ENTITY: Final = "pressure_entity"  # optional
CONF_ANEMOMETER_HEIGHT: Final = "anemometer_height_m"
# Latitude/elevation reuse homeassistant.const.CONF_LATITUDE / CONF_ELEVATION.

DEFAULT_ANEMOMETER_HEIGHT_M: Final = 2.0

# --- Zone subentry ------------------------------------------------------------
# Zone name reuses homeassistant.const.CONF_NAME.
CONF_AREA: Final = "area_m2"
CONF_CROP_PROFILE: Final = "crop_profile"
CONF_KC_MONTHLY: Final = "kc_monthly"  # list of 12 floats, January first
CONF_SOIL_TYPE: Final = "soil_type"
CONF_AWC: Final = "awc_mm_per_m"  # optional override (required for custom soil)
CONF_MAX_BLOCK: Final = "max_block_mm"  # optional override (required for custom soil)
CONF_ROOT_DEPTH: Final = "root_depth_mm"
CONF_DEPLETION_FRACTION: Final = "depletion_fraction"
CONF_RATE_MAINS: Final = "rate_mains_mm_per_min"
CONF_RATE_TANK: Final = "rate_tank_mm_per_min"
CONF_SOIL_MOISTURE_ENTITY: Final = "soil_moisture_entity"
CONF_SOIL_MOISTURE_DRY: Final = "soil_moisture_dry"
CONF_SOIL_MOISTURE_WET: Final = "soil_moisture_wet"

# Field names of the custom-Kc form step: kc_01 (January) ... kc_12 (December).
KC_MONTH_FIELDS: Final = tuple(f"kc_{month:02d}" for month in range(1, 13))

# --- Water sources -------------------------------------------------------
SOURCE_MAINS: Final = "mains"
SOURCE_TANK: Final = "tank"
SOURCE_RATE_KEYS: Final = {SOURCE_MAINS: CONF_RATE_MAINS, SOURCE_TANK: CONF_RATE_TANK}

# --- Options (operational, editable at any time) ---------------------------
CONF_RAIN_FACTOR: Final = "rain_effective_factor"
CONF_RAIN_THRESHOLD: Final = "rain_threshold_mm"
CONF_RUN_TIME: Final = "daily_run_time"
CONF_HARGREAVES_FALLBACK: Final = "hargreaves_fallback"
CONF_ADJUST_P_FOR_ETC: Final = "adjust_p_for_etc"
CONF_FORECAST_ENTITY: Final = "forecast_entity"  # optional
CONF_MIN_INTERVAL_HOURS: Final = "min_interval_hours"
CONF_WEEKLY_CAP: Final = "weekly_cap_mm"  # optional: absent = warning off
CONF_BLOCK_PAUSE: Final = "block_pause_minutes"

DEFAULT_RAIN_FACTOR: Final = 0.8
DEFAULT_RAIN_THRESHOLD_MM: Final = 2.0
DEFAULT_RUN_TIME: Final = "05:30:00"
DEFAULT_HARGREAVES_FALLBACK: Final = False
DEFAULT_ADJUST_P_FOR_ETC: Final = False
DEFAULT_MIN_INTERVAL_HOURS: Final = 48
DEFAULT_BLOCK_PAUSE_MINUTES: Final = 30

# --- Persistence -------------------------------------------------------------
STORAGE_VERSION: Final = 1
RETENTION_DAYS: Final = 365
