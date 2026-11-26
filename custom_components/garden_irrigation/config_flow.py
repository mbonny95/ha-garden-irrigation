"""Config flow for garden_irrigation.

- Main entry: weather source sensors and site parameters (one per install).
- Zone subentries: one per irrigated zone, added/edited from the
  integration page.
- Options: operational parameters, editable at any time.

Source sensors are validated for existence, a convertible unit and the
state_class the daily weather reader needs (it uses long-term statistics).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

import voluptuous as vol
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_NAME,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfIrradiance,
    UnitOfPrecipitationDepth,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.util.unit_conversion import (
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
)

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
    CONF_HUMIDITY_ENTITY,
    CONF_KC_MONTHLY,
    CONF_MAX_BLOCK,
    CONF_MIN_INTERVAL_HOURS,
    CONF_PRESSURE_ENTITY,
    CONF_RAIN_ENTITY,
    CONF_RAIN_FACTOR,
    CONF_RAIN_THRESHOLD,
    CONF_RATE_MAINS,
    CONF_RATE_TANK,
    CONF_ROOT_DEPTH,
    CONF_RUN_TIME,
    CONF_SOIL_MOISTURE_DRY,
    CONF_SOIL_MOISTURE_ENTITY,
    CONF_SOIL_MOISTURE_WET,
    CONF_SOIL_TYPE,
    CONF_SOLAR_RADIATION_ENTITY,
    CONF_TEMPERATURE_ENTITY,
    CONF_WEEKLY_CAP,
    CONF_WIND_SPEED_ENTITY,
    DEFAULT_ADJUST_P_FOR_ETC,
    DEFAULT_ANEMOMETER_HEIGHT_M,
    DEFAULT_BLOCK_PAUSE_MINUTES,
    DEFAULT_HARGREAVES_FALLBACK,
    DEFAULT_MIN_INTERVAL_HOURS,
    DEFAULT_RAIN_FACTOR,
    DEFAULT_RAIN_THRESHOLD_MM,
    DEFAULT_RUN_TIME,
    DOMAIN,
    KC_MONTH_FIELDS,
    SUBENTRY_TYPE_ZONE,
)
from .model.crops import (
    CROP_CUSTOM,
    DEFAULT_CROP,
    DEFAULT_DEPLETION_FRACTION,
    DEFAULT_ROOT_DEPTH_MM,
    KC_PROFILES,
)
from .model.soils import DEFAULT_SOIL, SOIL_CUSTOM, SOILS

ENTRY_TITLE = "Garden Irrigation"


# --- Source sensor validation -------------------------------------------------


@dataclass(frozen=True, slots=True)
class SensorSpec:
    """What a source sensor must provide to be usable."""

    units: frozenset[str]
    # Empty = any state_class (or none) is accepted.
    state_classes: frozenset[str] = frozenset()


_MEASUREMENT = frozenset({SensorStateClass.MEASUREMENT})


def _units(valid_units: Iterable[str | None]) -> frozenset[str]:
    return frozenset(unit for unit in valid_units if unit is not None)


WEATHER_SENSOR_SPECS: dict[str, SensorSpec] = {
    CONF_TEMPERATURE_ENTITY: SensorSpec(
        _units(TemperatureConverter.VALID_UNITS), _MEASUREMENT
    ),
    CONF_HUMIDITY_ENTITY: SensorSpec(frozenset({PERCENTAGE}), _MEASUREMENT),
    CONF_SOLAR_RADIATION_ENTITY: SensorSpec(
        frozenset({UnitOfIrradiance.WATTS_PER_SQUARE_METER}), _MEASUREMENT
    ),
    CONF_WIND_SPEED_ENTITY: SensorSpec(
        frozenset(u for u in UnitOfSpeed if u in SpeedConverter.VALID_UNITS),
        _MEASUREMENT,
    ),
    CONF_RAIN_ENTITY: SensorSpec(
        frozenset(
            {
                UnitOfPrecipitationDepth.MILLIMETERS,
                UnitOfPrecipitationDepth.CENTIMETERS,
                UnitOfPrecipitationDepth.INCHES,
            }
        ),
        frozenset({SensorStateClass.TOTAL, SensorStateClass.TOTAL_INCREASING}),
    ),
    CONF_PRESSURE_ENTITY: SensorSpec(
        _units(PressureConverter.VALID_UNITS), _MEASUREMENT
    ),
}

SOIL_MOISTURE_SPEC = SensorSpec(frozenset({PERCENTAGE}))


def validate_sensor(
    hass: HomeAssistant, entity_id: str, spec: SensorSpec
) -> str | None:
    """Return an error key if `entity_id` does not satisfy `spec`, else None."""
    state = hass.states.get(entity_id)
    if state is None:
        return "entity_not_found"
    if state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) not in spec.units:
        return "wrong_unit"
    if spec.state_classes and state.attributes.get(ATTR_STATE_CLASS) not in (
        spec.state_classes
    ):
        return "wrong_state_class"
    if state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        try:
            float(state.state)
        except ValueError:
            return "not_numeric"
    return None


def _validate_weather_sensors(
    hass: HomeAssistant, user_input: Mapping[str, Any]
) -> dict[str, str]:
    errors: dict[str, str] = {}
    for field, spec in WEATHER_SENSOR_SPECS.items():
        entity_id = user_input.get(field)
        if entity_id and (error := validate_sensor(hass, entity_id, spec)):
            errors[field] = error
    return errors


# --- Selector helpers --------------------------------------------------------------


def _number(
    minimum: float,
    maximum: float,
    step: float | Literal["any"],
    unit: str | None = None,
) -> selector.NumberSelector:
    config = selector.NumberSelectorConfig(
        min=minimum, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX
    )
    if unit is not None:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


def _select(options: list[str], translation_key: str) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            translation_key=translation_key,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


_SENSOR_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor")
)


# --- Main entry ---------------------------------------------------------------------


def _site_schema(hass: HomeAssistant) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_TEMPERATURE_ENTITY): _SENSOR_SELECTOR,
            vol.Required(CONF_HUMIDITY_ENTITY): _SENSOR_SELECTOR,
            vol.Required(CONF_SOLAR_RADIATION_ENTITY): _SENSOR_SELECTOR,
            vol.Required(CONF_WIND_SPEED_ENTITY): _SENSOR_SELECTOR,
            vol.Required(CONF_RAIN_ENTITY): _SENSOR_SELECTOR,
            vol.Optional(CONF_PRESSURE_ENTITY): _SENSOR_SELECTOR,
            vol.Required(
                CONF_ANEMOMETER_HEIGHT, default=DEFAULT_ANEMOMETER_HEIGHT_M
            ): _number(0.5, 20, 0.1, "m"),
            vol.Required(CONF_LATITUDE, default=hass.config.latitude): _number(
                -90, 90, "any", "°"
            ),
            vol.Required(CONF_ELEVATION, default=hass.config.elevation): _number(
                -500, 9000, 1, "m"
            ),
        }
    )


class GardenIrrigationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up the weather sources and site of the installation."""

    # v2 is a clean rewrite: v1 entries (VERSION 1) are intentionally not
    # migrated, so Home Assistant reports them instead of loading stale keys.
    VERSION = 2
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return GardenIrrigationOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Zones are subentries of the main entry."""
        return {SUBENTRY_TYPE_ZONE: ZoneSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the weather sensors and site parameters."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_weather_sensors(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title=ENTRY_TITLE, data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _site_schema(self.hass), user_input or {}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the weather sensors or site parameters."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_weather_sensors(self.hass, user_input)
            if not errors:
                return self.async_update_and_abort(entry, data=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _site_schema(self.hass), user_input or entry.data
            ),
            errors=errors,
        )


# --- Zone subentries ------------------------------------------------------------------


def _zone_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_AREA): _number(0.1, 100000, 0.1, "m²"),
            vol.Required(CONF_CROP_PROFILE, default=DEFAULT_CROP): _select(
                [*KC_PROFILES, CROP_CUSTOM], CONF_CROP_PROFILE
            ),
            vol.Required(CONF_SOIL_TYPE, default=DEFAULT_SOIL): _select(
                [*SOILS, SOIL_CUSTOM], CONF_SOIL_TYPE
            ),
            vol.Optional(CONF_AWC): _number(10, 400, 1, "mm/m"),
            vol.Optional(CONF_MAX_BLOCK): _number(1, 50, 0.5, "mm"),
            vol.Required(CONF_ROOT_DEPTH, default=DEFAULT_ROOT_DEPTH_MM): _number(
                20, 2000, 5, "mm"
            ),
            vol.Required(
                CONF_DEPLETION_FRACTION, default=DEFAULT_DEPLETION_FRACTION
            ): _number(0.1, 0.9, 0.05),
            vol.Optional(CONF_RATE_MAINS): _number(0.01, 10, 0.005, "mm/min"),
            vol.Optional(CONF_RATE_TANK): _number(0.01, 10, 0.005, "mm/min"),
            vol.Optional(CONF_SOIL_MOISTURE_ENTITY): _SENSOR_SELECTOR,
            vol.Optional(CONF_SOIL_MOISTURE_DRY): _number(0, 100, 1, "%"),
            vol.Optional(CONF_SOIL_MOISTURE_WET): _number(0, 100, 1, "%"),
        }
    )


def _kc_schema(defaults: list[float]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(field, default=defaults[index]): _number(0.1, 1.5, 0.01)
            for index, field in enumerate(KC_MONTH_FIELDS)
        }
    )


class ZoneSubentryFlow(ConfigSubentryFlow):
    """Add or edit an irrigated zone."""

    def __init__(self) -> None:
        """Hold the zone data collected across steps."""
        self._zone: dict[str, Any] = {}

    @property
    def _is_reconfigure(self) -> bool:
        return self.source == SOURCE_RECONFIGURE

    def _current(self) -> dict[str, Any]:
        if self._is_reconfigure:
            return dict(self._get_reconfigure_subentry().data)
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new zone."""
        return await self._async_step_zone("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing zone."""
        return await self._async_step_zone("reconfigure", user_input)

    async def _async_step_zone(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_NAME] = user_input[CONF_NAME].strip()
            errors = self._validate_zone(user_input)
            if not errors:
                self._zone = dict(user_input)
                if user_input[CONF_CROP_PROFILE] == CROP_CUSTOM:
                    return await self.async_step_kc()
                return self._async_finish()
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                _zone_schema(),
                user_input if user_input is not None else self._current(),
            ),
            errors=errors,
        )

    async def async_step_kc(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Enter a custom monthly Kc profile."""
        if user_input is not None:
            self._zone[CONF_KC_MONTHLY] = [
                float(user_input[field]) for field in KC_MONTH_FIELDS
            ]
            return self._async_finish()
        defaults = self._current().get(CONF_KC_MONTHLY) or list(
            KC_PROFILES[DEFAULT_CROP]
        )
        return self.async_show_form(step_id="kc", data_schema=_kc_schema(defaults))

    def _validate_zone(self, user_input: Mapping[str, Any]) -> dict[str, str]:
        errors: dict[str, str] = {}

        name: str = user_input[CONF_NAME]
        own_id = (
            self._get_reconfigure_subentry().subentry_id
            if (self._is_reconfigure)
            else None
        )
        other_names = {
            subentry.title.casefold()
            for subentry_id, subentry in self._get_entry().subentries.items()
            if subentry.subentry_type == SUBENTRY_TYPE_ZONE and subentry_id != own_id
        }
        if not name:
            errors[CONF_NAME] = "name_required"
        elif name.casefold() in other_names:
            errors[CONF_NAME] = "name_exists"

        if user_input[CONF_SOIL_TYPE] == SOIL_CUSTOM:
            for field in (CONF_AWC, CONF_MAX_BLOCK):
                if user_input.get(field) is None:
                    errors[field] = "required_for_custom_soil"

        if user_input.get(CONF_RATE_MAINS) is None and (
            user_input.get(CONF_RATE_TANK) is None
        ):
            errors["base"] = "no_rate"

        sensor = user_input.get(CONF_SOIL_MOISTURE_ENTITY)
        dry = user_input.get(CONF_SOIL_MOISTURE_DRY)
        wet = user_input.get(CONF_SOIL_MOISTURE_WET)
        if sensor:
            if error := validate_sensor(self.hass, sensor, SOIL_MOISTURE_SPEC):
                errors[CONF_SOIL_MOISTURE_ENTITY] = error
        elif dry is not None or wet is not None:
            errors[CONF_SOIL_MOISTURE_ENTITY] = "thresholds_without_sensor"
        if dry is not None and wet is not None and dry >= wet:
            errors[CONF_SOIL_MOISTURE_DRY] = "dry_not_below_wet"

        return errors

    def _async_finish(self) -> SubentryFlowResult:
        if self._zone[CONF_CROP_PROFILE] != CROP_CUSTOM:
            # Preset profiles are resolved at runtime, so improved defaults
            # reach existing zones without a migration.
            self._zone.pop(CONF_KC_MONTHLY, None)
        title: str = self._zone[CONF_NAME]
        if self._is_reconfigure:
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                title=title,
                data=self._zone,
            )
        return self.async_create_entry(title=title, data=self._zone)


# --- Options ------------------------------------------------------------------------

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_RAIN_FACTOR, default=DEFAULT_RAIN_FACTOR): _number(
            0, 1, 0.05
        ),
        vol.Required(CONF_RAIN_THRESHOLD, default=DEFAULT_RAIN_THRESHOLD_MM): _number(
            0, 20, 0.5, "mm"
        ),
        vol.Required(CONF_RUN_TIME, default=DEFAULT_RUN_TIME): selector.TimeSelector(),
        vol.Required(
            CONF_HARGREAVES_FALLBACK, default=DEFAULT_HARGREAVES_FALLBACK
        ): selector.BooleanSelector(),
        vol.Required(
            CONF_ADJUST_P_FOR_ETC, default=DEFAULT_ADJUST_P_FOR_ETC
        ): selector.BooleanSelector(),
        vol.Optional(CONF_FORECAST_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="weather")
        ),
        vol.Required(
            CONF_MIN_INTERVAL_HOURS, default=DEFAULT_MIN_INTERVAL_HOURS
        ): _number(0, 336, 1, "h"),
        vol.Optional(CONF_WEEKLY_CAP): _number(1, 200, 1, "mm"),
        vol.Required(CONF_BLOCK_PAUSE, default=DEFAULT_BLOCK_PAUSE_MINUTES): _number(
            0, 240, 5, "min"
        ),
    }
)


class GardenIrrigationOptionsFlow(OptionsFlow):
    """Edit the operational parameters."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the options form."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
