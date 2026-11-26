"""Actions: record an irrigation, set a zone's deficit."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, SOURCE_MAINS, SOURCE_TANK
from .coordinator import (
    MAX_IRRIGATION_MINUTES,
    MAX_IRRIGATION_MM,
    GardenIrrigationCoordinator,
)

SERVICE_RECORD_IRRIGATION = "record_irrigation"
SERVICE_SET_DEFICIT = "set_deficit"

ATTR_ZONE = "zone"
ATTR_SOURCE = "source"
ATTR_MINUTES = "minutes"
ATTR_MM = "mm"
ATTR_NOTE = "note"
ATTR_DEFICIT = "deficit_mm"

RECORD_IRRIGATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ZONE): cv.string,
        vol.Required(ATTR_SOURCE): vol.In([SOURCE_MAINS, SOURCE_TANK]),
        vol.Optional(ATTR_MINUTES): vol.All(
            vol.Coerce(float), vol.Range(min=0.1, max=MAX_IRRIGATION_MINUTES)
        ),
        vol.Optional(ATTR_MM): vol.All(
            vol.Coerce(float), vol.Range(min=0.1, max=MAX_IRRIGATION_MM)
        ),
        vol.Optional(ATTR_NOTE): cv.string,
    }
)

SET_DEFICIT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ZONE): cv.string,
        vol.Required(ATTR_DEFICIT): vol.All(vol.Coerce(float), vol.Range(min=0)),
    }
)


def _resolve_zone(
    hass: HomeAssistant, device_id: str
) -> tuple[GardenIrrigationCoordinator, str]:
    """Map a zone device to its loaded coordinator and zone (subentry) id."""
    device = dr.async_get(hass).async_get(device_id)
    if device is not None:
        for entry_id, subentry_ids in device.config_entries_subentries.items():
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None or entry.domain != DOMAIN:
                continue
            if entry.state is not ConfigEntryState.LOADED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="not_loaded"
                )
            coordinator: GardenIrrigationCoordinator = entry.runtime_data.coordinator
            for subentry_id in subentry_ids:
                if subentry_id in coordinator.zones:
                    return coordinator, subentry_id
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="invalid_zone"
    )


async def _async_record_irrigation(call: ServiceCall) -> ServiceResponse:
    coordinator, zone_id = _resolve_zone(call.hass, call.data[ATTR_ZONE])
    record = await coordinator.async_record_irrigation(
        zone_id,
        call.data[ATTR_SOURCE],
        minutes=call.data.get(ATTR_MINUTES),
        mm=call.data.get(ATTR_MM),
        note=call.data.get(ATTR_NOTE),
    )
    response: dict[str, Any] = dict(record)
    return response


async def _async_set_deficit(call: ServiceCall) -> None:
    coordinator, zone_id = _resolve_zone(call.hass, call.data[ATTR_ZONE])
    await coordinator.async_set_deficit(zone_id, call.data[ATTR_DEFICIT])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions (once, not per entry)."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECORD_IRRIGATION,
        _async_record_irrigation,
        schema=RECORD_IRRIGATION_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DEFICIT,
        _async_set_deficit,
        schema=SET_DEFICIT_SCHEMA,
    )
