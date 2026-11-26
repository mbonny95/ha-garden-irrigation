"""Runtime data attached to the config entry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

from .store import GardenIrrigationStore

if TYPE_CHECKING:
    from .coordinator import GardenIrrigationCoordinator


@dataclass(slots=True)
class GardenIrrigationRuntimeData:
    """Objects that live as long as the config entry is loaded."""

    store: GardenIrrigationStore
    coordinator: GardenIrrigationCoordinator


type GardenIrrigationConfigEntry = ConfigEntry[GardenIrrigationRuntimeData]
