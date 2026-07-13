"""Coordinator for garden_irrigation.

Milestone 2 adds the WeatherAggregator (accumulators + persistence + a bounded
recorder backfill), owned here as `coordinator.weather`. No ET0/balance/
recommendation computation happens yet — `_async_update_data` is still the
Milestone 1 placeholder; later milestones make it consume `self.weather`
without changing this class's shape.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DATA_QUALITY_INITIALIZING, DOMAIN
from .weather import WeatherAggregator

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
        self.weather = WeatherAggregator(hass, entry)

    async def async_setup(self) -> None:
        """Start the weather aggregator's listeners (restore/backfill first)."""
        await self.weather.async_setup()

    async def async_shutdown(self) -> None:
        """Stop the weather aggregator's listeners and force a final flush.

        Extends (not replaces) DataUpdateCoordinator.async_shutdown, which
        also cancels the coordinator's own scheduled refresh/debouncer.
        """
        await self.weather.async_shutdown()
        await super().async_shutdown()

    async def _async_update_data(self) -> dict[str, Any]:
        """Placeholder refresh: no real computation happens before Milestone 3."""
        return {"data_quality": DATA_QUALITY_INITIALIZING}
