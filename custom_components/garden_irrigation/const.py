"""Constants for the garden_irrigation integration.

Config-flow keys and defaults, plus the storage key shared by every engine
that persists state (weather.py in Milestone 2; balance/irrigation_log in
later milestones). Agronomy/weather computation constants (FAO-56, balance
thresholds, etc.) are declared here already because the config/options
schema depends on them, but the engines that consume them are implemented in
later milestones (see CLAUDE.md).
"""

from __future__ import annotations

from homeassistant.const import (
    PERCENTAGE,
    UnitOfIrradiance,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)

DOMAIN = "garden_irrigation"

# --- Persistent storage ------------------------------------------------------
# Single "state" Store shared by every engine (weather accumulators here in
# Milestone 2; per-zone deficit and event-log metadata in later milestones).
# Each engine owns its own top-level key within the stored dict.
STORAGE_KEY_STATE = f"{DOMAIN}.state"
# Milestone 4's water balance uses its OWN store file rather than sharing the
# key above: WeatherAggregator caches the OTHER top-level keys it doesn't own
# as a frozen-at-setup snapshot and rewrites them on every debounced save
# (weather.py, not modifiable in M4), so a second engine writing into the same
# file would have its updates silently dropped by the next weather autosave.
STORAGE_KEY_BALANCE = f"{DOMAIN}.balance_state"
# Milestone 6's manual irrigation-cycle log is the "events" store from
# CLAUDE.md (365-day retention) - a third file, for the same reason as
# STORAGE_KEY_BALANCE above: it's exclusively owned by irrigation_log.py, so
# there is no cross-engine merge-on-save race to worry about.
STORAGE_KEY_EVENTS = f"{DOMAIN}.events"
# Milestone 7's WH51 calibration baseline (first-seen timestamp + observed
# min/max per zone) is its own store file too, for the same isolation reason.
STORAGE_KEY_RECOMMENDATION = f"{DOMAIN}.recommendation_state"
# Milestone 9's operational state (select.mode, the declared-cycle zone/
# start timestamp) is its own store file too, same isolation reason - owned
# by coordinator.py, read/written by select.py/button.py through it.
STORAGE_KEY_OPERATIONAL = f"{DOMAIN}.operational_state"

# --- Sources -----------------------------------------------------------------
# No automated fallback between sources exists or is planned: the user always
# confirms the source manually when recording a cycle.
SOURCE_RAINWATER_TANK = "rainwater_tank"
SOURCE_MAINS_WATER = "mains_water"
SOURCES = [SOURCE_RAINWATER_TANK, SOURCE_MAINS_WATER]

# --- Modes ---------------------------------------------------------------
# v1 exposes ONLY these two modes. There is no "automation" mode, not even as
# a disabled placeholder: actuation is out of scope until a future phase.
MODE_CALIBRATION = "calibration"
MODE_MONITORING = "monitoring"
MODES = [MODE_CALIBRATION, MODE_MONITORING]

# --- Zones -----------------------------------------------------------------
# v1 has exactly two fixed, sequential zones. Modeled as a list so a future
# phase can support N zones/subentries without a data-model migration.
ZONE_1 = "zone_1"
ZONE_2 = "zone_2"
ZONES = [ZONE_1, ZONE_2]

# --- Config flow step ids ----------------------------------------------------
STEP_WEATHER = "user"
STEP_RAIN = "rain"
STEP_SOIL = "soil"
STEP_ZONES = "zones"

# --- Config keys: position & FAO-56 weather inputs (step a) -----------------
CONF_ALTITUDE = "altitude"
CONF_ANEMOMETER_HEIGHT = "anemometer_height"
CONF_TEMPERATURE_ENTITY = "temperature_entity"
CONF_HUMIDITY_ENTITY = "humidity_entity"
CONF_PRESSURE_ENTITY = "pressure_entity"
CONF_SOLAR_RADIATION_ENTITY = "solar_radiation_entity"
CONF_WIND_SPEED_ENTITY = "wind_speed_entity"
CONF_WIND_GUST_ENTITY = "wind_gust_entity"  # optional, NOT required for ET0

# --- Config keys: rain (step b) ----------------------------------------------
# daily_rainfall and rain_rate are both mandatory (rain_rate is needed for the
# "stop watering" advisory during a declared manual cycle, not only for ET0).
CONF_DAILY_RAINFALL_ENTITY = "daily_rainfall_entity"
CONF_RAIN_RATE_ENTITY = "rain_rate_entity"
CONF_RAIN_24H_ENTITY = "rain_24h_entity"  # optional/diagnostic only
CONF_RAIN_EVENT_ENTITY = "rain_event_entity"  # optional/diagnostic only

# --- Config keys: WH51 per zone (step c) -------------------------------------
CONF_ZONE1_SOIL_MOISTURE_ENTITY = "zone1_soil_moisture_entity"
CONF_ZONE1_BATTERY_ENTITY = "zone1_battery_entity"  # optional
CONF_ZONE1_SIGNAL_ENTITY = "zone1_signal_entity"  # optional
CONF_ZONE2_SOIL_MOISTURE_ENTITY = "zone2_soil_moisture_entity"
CONF_ZONE2_BATTERY_ENTITY = "zone2_battery_entity"  # optional
CONF_ZONE2_SIGNAL_ENTITY = "zone2_signal_entity"  # optional

# --- Config keys: zone names/areas/distribution (step d) --------------------
CONF_ZONE1_NAME = "zone1_name"
CONF_ZONE1_AREA_M2 = "zone1_area_m2"
CONF_ZONE1_MM_PER_MIN_MAINS = "zone1_mm_per_minute_mains"
CONF_ZONE1_MM_PER_MIN_TANK = "zone1_mm_per_minute_tank"  # nullable: not calibrated
CONF_ZONE1_FLOW_RATE_MAINS_LPM = "zone1_flow_rate_mains_lpm"
CONF_ZONE2_NAME = "zone2_name"
CONF_ZONE2_AREA_M2 = "zone2_area_m2"
CONF_ZONE2_MM_PER_MIN_MAINS = "zone2_mm_per_minute_mains"
CONF_ZONE2_MM_PER_MIN_TANK = "zone2_mm_per_minute_tank"  # nullable: not calibrated
CONF_ZONE2_FLOW_RATE_MAINS_LPM = "zone2_flow_rate_mains_lpm"

# --- Defaults: position -------------------------------------------------
DEFAULT_ALTITUDE_M = 116
DEFAULT_ANEMOMETER_HEIGHT_M = 2.0

# --- Defaults: zones (initial, user-recalibratable from options) -----------
DEFAULT_ZONE1_NAME = "Zona 1"
DEFAULT_ZONE1_AREA_M2 = 38
DEFAULT_ZONE1_MM_PER_MIN_MAINS = 0.25
DEFAULT_ZONE1_FLOW_RATE_MAINS_LPM = 9.5
DEFAULT_ZONE2_NAME = "Zona 2"
DEFAULT_ZONE2_AREA_M2 = 72
DEFAULT_ZONE2_MM_PER_MIN_MAINS = 0.175
DEFAULT_ZONE2_FLOW_RATE_MAINS_LPM = 12.6

# --- Defaults: soil / agronomy (options, future milestones) -----------------
DEFAULT_KC = 0.95
DEFAULT_ROOT_DEPTH_MM = 150
DEFAULT_AWC_MM_PER_M = 200
DEFAULT_P_DEPLETION_FRACTION = 0.5
DEFAULT_RAIN_EFFECTIVE_FACTOR = 0.8

# --- Defaults: limits (options, future milestones) --------------------------
# The 30 mm cap governs ONLY user-recorded irrigation over a sliding 7x24h
# window. Effective rain is shown separately and never consumes this cap.
DEFAULT_WEEKLY_CAP_MM = 30
DEFAULT_MIN_INTERVAL_HOURS = 48
DEFAULT_MAX_CYCLE_MINUTES = 15
# Pause between successive ≤15-minute blocks of a multi-block recommended
# cycle (Milestone 7 recommendation.py), to let water infiltrate and avoid
# runoff before the next block starts.
DEFAULT_BLOCK_PAUSE_MINUTES = 10

# --- Defaults: WH51 soft-signal thresholds (options, future milestones) -----
# Device-relative position within the observed [baseline_min, baseline_max]
# range (0 = driest ever observed, 1 = wettest ever observed) - NOT absolute
# VWC. Only used as a soft, explainable corroborating signal once calibration
# (DEFAULT_CALIBRATION_DAYS) is complete - never a hard block (CLAUDE.md §1.9).
DEFAULT_WH51_CRITICAL_THRESHOLD = 0.1
DEFAULT_WH51_DRY_THRESHOLD = 0.3
DEFAULT_WH51_WET_THRESHOLD = 0.7

# --- Defaults: wind warnings (options, future milestones) -------------------
DEFAULT_WIND_WARNING_AVG_KMH = 15
DEFAULT_WIND_WARNING_GUST_KMH = 25

# --- Defaults: staleness thresholds (options, future milestones) -----------
DEFAULT_STALE_WH51_WARNING_HOURS = 3
DEFAULT_STALE_WH51_ERROR_HOURS = 12
DEFAULT_STALE_WEATHER_WARNING_MINUTES = 30
DEFAULT_STALE_WEATHER_ERROR_HOURS = 2

# --- Defaults: WH51 battery/signal advisory thresholds (Milestone 8) -------
# CLAUDE.md/the plan do not give exact numbers for these two (unlike the
# wind/staleness thresholds above) - these are reasonable, documented
# defaults pending a future options-flow override: battery is a percentage
# (see config_flow's battery entity, PERCENTAGE unit); signal follows the
# common Ecowitt/WH51 0-4 bar-style scale.
DEFAULT_WH51_BATTERY_WARNING_PERCENT = 20
DEFAULT_WH51_SIGNAL_WARNING = 1

# --- Defaults: rain accumulator (options, future milestones) ---------------
DEFAULT_RAIN_RESET_TOLERANCE_MM = 0.1

# --- Defaults: calibration & scheduling (options, future milestones) -------
DEFAULT_CALIBRATION_DAYS = 14
DEFAULT_EVENING_CHECK_TIME = "20:00:00"
DEFAULT_MORNING_CHECK_TIME = "05:30:00"

# --- Expected units for entity validation (config_flow / validation.py) ----
# Typed as set[str] (not set[UnitOfX]): mypy sets are invariant, and
# validate_sensor_entity() compares against a plain str state attribute.
UNIT_TEMPERATURE: set[str] = {UnitOfTemperature.CELSIUS}
UNIT_HUMIDITY: set[str] = {PERCENTAGE}
UNIT_PRESSURE: set[str] = {UnitOfPressure.HPA}
UNIT_IRRADIANCE: set[str] = {UnitOfIrradiance.WATTS_PER_SQUARE_METER}
UNIT_SPEED: set[str] = {UnitOfSpeed.KILOMETERS_PER_HOUR}
UNIT_RAIN_DEPTH: set[str] = {UnitOfPrecipitationDepth.MILLIMETERS}
UNIT_RAIN_RATE: set[str] = {UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR}
UNIT_PERCENTAGE: set[str] = {PERCENTAGE}

# --- data_quality sensor states ---------------------------------------------
# Milestone 1 exposes ONLY these two states. Real availability/data-quality
# logic (stale weather/WH51, battery, signal, etc.) arrives in Milestone 2 —
# do not anticipate it here.
DATA_QUALITY_INITIALIZING = "initializing"
DATA_QUALITY_NOT_CONFIGURED = "not_configured"
DATA_QUALITY_STATES = [DATA_QUALITY_INITIALIZING, DATA_QUALITY_NOT_CONFIGURED]

# --- Diagnostic sensor exposed by a declared manual cycle (Milestone 9) -----
# Read-only elapsed time; NEVER used to prefill the manual-record form.
SENSOR_KEY_ELAPSED_MANUAL_CYCLE_MINUTES = "elapsed_manual_cycle_minutes"
