"""Runtime data attached to the config entry."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .store import GardenIrrigationStore


@dataclass(slots=True)
class GardenIrrigationRuntimeData:
    """Objects that live as long as the config entry is loaded."""

    store: GardenIrrigationStore


type GardenIrrigationConfigEntry = ConfigEntry[GardenIrrigationRuntimeData]
