"""Config flow for garden_irrigation.

Five ordered steps, per the approved plan:
  (a) user     - position + FAO-56 weather inputs (wind_gust is optional)
  (b) rain     - daily_rainfall and rain_rate are mandatory; 24h/event optional
  (c) soil     - WH51 soil moisture per zone (battery/signal optional)
  (d) zones    - zone names/areas/distribution (mm/min mains + tank, nullable)
  (e) telegram - fully optional and skippable, completable later from options

No Ecowitt entity names are hardcoded anywhere in this module: the user always
picks entities via an EntitySelector.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ALTITUDE,
    CONF_ANEMOMETER_HEIGHT,
    CONF_DAILY_RAINFALL_ENTITY,
    CONF_HUMIDITY_ENTITY,
    CONF_PRESSURE_ENTITY,
    CONF_RAIN_24H_ENTITY,
    CONF_RAIN_EVENT_ENTITY,
    CONF_RAIN_RATE_ENTITY,
    CONF_SOLAR_RADIATION_ENTITY,
    CONF_TELEGRAM_CHAT_ID,
    CONF_TELEGRAM_CONFIG_ENTRY_ID,
    CONF_TELEGRAM_ENTITY_ID,
    CONF_TEMPERATURE_ENTITY,
    CONF_WIND_GUST_ENTITY,
    CONF_WIND_SPEED_ENTITY,
    CONF_ZONE1_AREA_M2,
    CONF_ZONE1_BATTERY_ENTITY,
    CONF_ZONE1_FLOW_RATE_MAINS_LPM,
    CONF_ZONE1_MM_PER_MIN_MAINS,
    CONF_ZONE1_MM_PER_MIN_TANK,
    CONF_ZONE1_NAME,
    CONF_ZONE1_SIGNAL_ENTITY,
    CONF_ZONE1_SOIL_MOISTURE_ENTITY,
    CONF_ZONE2_AREA_M2,
    CONF_ZONE2_BATTERY_ENTITY,
    CONF_ZONE2_FLOW_RATE_MAINS_LPM,
    CONF_ZONE2_MM_PER_MIN_MAINS,
    CONF_ZONE2_MM_PER_MIN_TANK,
    CONF_ZONE2_NAME,
    CONF_ZONE2_SIGNAL_ENTITY,
    CONF_ZONE2_SOIL_MOISTURE_ENTITY,
    DEFAULT_ALTITUDE_M,
    DEFAULT_ANEMOMETER_HEIGHT_M,
    DEFAULT_ZONE1_AREA_M2,
    DEFAULT_ZONE1_FLOW_RATE_MAINS_LPM,
    DEFAULT_ZONE1_MM_PER_MIN_MAINS,
    DEFAULT_ZONE1_NAME,
    DEFAULT_ZONE2_AREA_M2,
    DEFAULT_ZONE2_FLOW_RATE_MAINS_LPM,
    DEFAULT_ZONE2_MM_PER_MIN_MAINS,
    DEFAULT_ZONE2_NAME,
    DOMAIN,
    STEP_RAIN,
    STEP_SOIL,
    STEP_TELEGRAM,
    STEP_WEATHER,
    STEP_ZONES,
    UNIT_HUMIDITY,
    UNIT_IRRADIANCE,
    UNIT_PRESSURE,
    UNIT_RAIN_DEPTH,
    UNIT_RAIN_RATE,
    UNIT_SPEED,
    UNIT_TEMPERATURE,
)
from .validation import EntityValidationError, validate_sensor_entity


def _entity_selector(domain: str | None = None) -> selector.EntitySelector:
    """Build an entity picker.

    No domain filter by default: the selector itself must not hard-reject a
    wrong-domain entity_id (it would raise a raw schema exception before our
    step handler runs). Domain/unit/existence are instead enforced by
    validate_sensor_entity(), which produces a friendly per-field form error.
    """
    config: selector.EntitySelectorConfig = {}
    if domain is not None:
        config["domain"] = domain
    return selector.EntitySelector(config)


def _validate_fields(
    hass: Any,
    user_input: dict[str, Any],
    field_units: dict[str, set[str] | None],
) -> dict[str, str]:
    """Validate a set of entity_id fields; return an errors dict for the form."""
    errors: dict[str, str] = {}
    for field, expected_units in field_units.items():
        entity_id = user_input.get(field)
        if not entity_id:
            continue
        try:
            validate_sensor_entity(hass, entity_id, expected_units=expected_units)
        except EntityValidationError as err:
            errors[field] = err.reason
    return errors


class GardenIrrigationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the guided, multi-step setup of garden_irrigation."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the accumulator for data collected across steps."""
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> Any:
        """Step (a): position + FAO-56 weather inputs."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_fields(
                self.hass,
                user_input,
                {
                    CONF_TEMPERATURE_ENTITY: UNIT_TEMPERATURE,
                    CONF_HUMIDITY_ENTITY: UNIT_HUMIDITY,
                    CONF_PRESSURE_ENTITY: UNIT_PRESSURE,
                    CONF_SOLAR_RADIATION_ENTITY: UNIT_IRRADIANCE,
                    CONF_WIND_SPEED_ENTITY: UNIT_SPEED,
                    CONF_WIND_GUST_ENTITY: UNIT_SPEED,
                },
            )
            if not errors:
                self._data.update(user_input)
                return await self.async_step_rain()

        default_altitude = self.hass.config.elevation or DEFAULT_ALTITUDE_M
        schema = vol.Schema(
            {
                vol.Required(CONF_ALTITUDE, default=default_altitude): vol.Coerce(
                    float
                ),
                vol.Required(
                    CONF_ANEMOMETER_HEIGHT, default=DEFAULT_ANEMOMETER_HEIGHT_M
                ): vol.Coerce(float),
                vol.Required(CONF_TEMPERATURE_ENTITY): _entity_selector(),
                vol.Required(CONF_HUMIDITY_ENTITY): _entity_selector(),
                vol.Required(CONF_PRESSURE_ENTITY): _entity_selector(),
                vol.Required(CONF_SOLAR_RADIATION_ENTITY): _entity_selector(),
                vol.Required(CONF_WIND_SPEED_ENTITY): _entity_selector(),
                vol.Optional(CONF_WIND_GUST_ENTITY): _entity_selector(),
            }
        )
        return self.async_show_form(
            step_id=STEP_WEATHER, data_schema=schema, errors=errors
        )

    async def async_step_rain(self, user_input: dict[str, Any] | None = None) -> Any:
        """Step (b): rain entities. daily_rainfall and rain_rate are mandatory."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_fields(
                self.hass,
                user_input,
                {
                    CONF_DAILY_RAINFALL_ENTITY: UNIT_RAIN_DEPTH,
                    CONF_RAIN_RATE_ENTITY: UNIT_RAIN_RATE,
                    CONF_RAIN_24H_ENTITY: UNIT_RAIN_DEPTH,
                    CONF_RAIN_EVENT_ENTITY: UNIT_RAIN_DEPTH,
                },
            )
            if not errors:
                self._data.update(user_input)
                return await self.async_step_soil()

        schema = vol.Schema(
            {
                vol.Required(CONF_DAILY_RAINFALL_ENTITY): _entity_selector(),
                vol.Required(CONF_RAIN_RATE_ENTITY): _entity_selector(),
                vol.Optional(CONF_RAIN_24H_ENTITY): _entity_selector(),
                vol.Optional(CONF_RAIN_EVENT_ENTITY): _entity_selector(),
            }
        )
        return self.async_show_form(
            step_id=STEP_RAIN, data_schema=schema, errors=errors
        )

    async def async_step_soil(self, user_input: dict[str, Any] | None = None) -> Any:
        """Step (c): WH51 soil moisture per zone; battery/signal optional."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_fields(
                self.hass,
                user_input,
                {
                    CONF_ZONE1_SOIL_MOISTURE_ENTITY: UNIT_HUMIDITY,
                    CONF_ZONE1_BATTERY_ENTITY: None,
                    CONF_ZONE1_SIGNAL_ENTITY: None,
                    CONF_ZONE2_SOIL_MOISTURE_ENTITY: UNIT_HUMIDITY,
                    CONF_ZONE2_BATTERY_ENTITY: None,
                    CONF_ZONE2_SIGNAL_ENTITY: None,
                },
            )
            if not errors:
                self._data.update(user_input)
                return await self.async_step_zones()

        schema = vol.Schema(
            {
                vol.Required(CONF_ZONE1_SOIL_MOISTURE_ENTITY): _entity_selector(),
                vol.Optional(CONF_ZONE1_BATTERY_ENTITY): _entity_selector(),
                vol.Optional(CONF_ZONE1_SIGNAL_ENTITY): _entity_selector(),
                vol.Required(CONF_ZONE2_SOIL_MOISTURE_ENTITY): _entity_selector(),
                vol.Optional(CONF_ZONE2_BATTERY_ENTITY): _entity_selector(),
                vol.Optional(CONF_ZONE2_SIGNAL_ENTITY): _entity_selector(),
            }
        )
        return self.async_show_form(
            step_id=STEP_SOIL, data_schema=schema, errors=errors
        )

    async def async_step_zones(self, user_input: dict[str, Any] | None = None) -> Any:
        """Step (d): zone names/areas/distribution. Tank rate may be null."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_telegram()

        schema = vol.Schema(
            {
                vol.Required(CONF_ZONE1_NAME, default=DEFAULT_ZONE1_NAME): str,
                vol.Required(
                    CONF_ZONE1_AREA_M2, default=DEFAULT_ZONE1_AREA_M2
                ): vol.Coerce(float),
                vol.Required(
                    CONF_ZONE1_MM_PER_MIN_MAINS,
                    default=DEFAULT_ZONE1_MM_PER_MIN_MAINS,
                ): vol.Coerce(float),
                vol.Optional(CONF_ZONE1_MM_PER_MIN_TANK): vol.Coerce(float),
                vol.Required(
                    CONF_ZONE1_FLOW_RATE_MAINS_LPM,
                    default=DEFAULT_ZONE1_FLOW_RATE_MAINS_LPM,
                ): vol.Coerce(float),
                vol.Required(CONF_ZONE2_NAME, default=DEFAULT_ZONE2_NAME): str,
                vol.Required(
                    CONF_ZONE2_AREA_M2, default=DEFAULT_ZONE2_AREA_M2
                ): vol.Coerce(float),
                vol.Required(
                    CONF_ZONE2_MM_PER_MIN_MAINS,
                    default=DEFAULT_ZONE2_MM_PER_MIN_MAINS,
                ): vol.Coerce(float),
                vol.Optional(CONF_ZONE2_MM_PER_MIN_TANK): vol.Coerce(float),
                vol.Required(
                    CONF_ZONE2_FLOW_RATE_MAINS_LPM,
                    default=DEFAULT_ZONE2_FLOW_RATE_MAINS_LPM,
                ): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id=STEP_ZONES, data_schema=schema)

    async def async_step_telegram(
        self, user_input: dict[str, Any] | None = None
    ) -> Any:
        """Step (e): Telegram target, fully optional and skippable."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="Garden Irrigation", data=self._data)

        schema = vol.Schema(
            {
                vol.Optional(CONF_TELEGRAM_ENTITY_ID): _entity_selector(
                    domain="notify"
                ),
                vol.Optional(CONF_TELEGRAM_CONFIG_ENTRY_ID): str,
                vol.Optional(CONF_TELEGRAM_CHAT_ID): str,
            }
        )
        return self.async_show_form(step_id=STEP_TELEGRAM, data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> GardenIrrigationOptionsFlow:
        """Return the options flow handler for this config entry."""
        return GardenIrrigationOptionsFlow()


class GardenIrrigationOptionsFlow(OptionsFlow):
    """Minimal pass-through options flow stub.

    The full operational options set (Kc, thresholds, caps, Telegram, ...)
    lands in later milestones; Milestone 1 only proves the flow opens and
    saves.
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> Any:
        """Show an (empty, for now) options form and save on submit."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=vol.Schema({}))
