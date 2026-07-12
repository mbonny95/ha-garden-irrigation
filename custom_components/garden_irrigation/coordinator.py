"""Skeleton coordinator for garden_irrigation.

Milestone 1: no weather aggregation, no ET0/balance/recommendation computation.
The coordinator exists so entities have a single, event-driven data source to
subscribe to from the start; the real engines are wired in from Milestone 2
onward without changing this shape.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DATA_QUALITY_INITIALIZING, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GardenIrrigationCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Event-driven coordinator (no polling: update_interval is None).

    Refreshes are triggered by state-change listeners (weather/WH51 entities)
    and by the 20:00/05:30 scheduler in later milestones — never by a fixed
    interval.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator for a single config entry."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
        )
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        """Placeholder refresh: no real computation happens in Milestone 1."""
        return {"data_quality": DATA_QUALITY_INITIALIZING}
