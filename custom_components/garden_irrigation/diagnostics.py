"""Diagnostics download: configuration, persisted state and current data."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_LATITUDE
from homeassistant.core import HomeAssistant

from .data import GardenIrrigationConfigEntry

# Latitude is the only location hint in the configuration.
TO_REDACT = {CONF_LATITUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GardenIrrigationConfigEntry
) -> dict[str, Any]:
    """Return everything needed to understand a recommendation."""
    coordinator = entry.runtime_data.coordinator
    store = entry.runtime_data.store
    data = coordinator.data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
            "zones": {
                subentry_id: {"title": subentry.title, "data": dict(subentry.data)}
                for subentry_id, subentry in entry.subentries.items()
            },
        },
        "store": {
            "last_weather_day": store.last_weather_day,
            "zones": {zone_id: store.zone(zone_id) for zone_id in store.zone_ids()},
        },
        "data": {
            "forecast": asdict(data.forecast) if data.forecast else None,
            "zones": {
                zone_id: {
                    "deficit_mm": snapshot.deficit_mm,
                    "closed_deficit_mm": snapshot.closed_deficit_mm,
                    "taw_mm": snapshot.soil.taw_mm,
                    "raw_mm": snapshot.soil.raw_mm,
                    "kc_today": snapshot.kc_today,
                    "soil_sensor": (
                        asdict(snapshot.soil_sensor) if snapshot.soil_sensor else None
                    ),
                    "recommendation": asdict(snapshot.recommendation),
                }
                for zone_id, snapshot in data.zones.items()
            },
        },
    }
