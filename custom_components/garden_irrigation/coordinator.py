"""Coordinator for garden_irrigation.

Milestone 2 added the WeatherAggregator (accumulators + persistence + a
bounded recorder backfill), owned here as `coordinator.weather`. Milestone 3
adds ET0 computation for the current (in-progress) day from that aggregator's
live snapshot, exposed as `coordinator.data["et0"]`. Per-zone water balance
and the recommendation engine are NOT started here (see balance.py /
recommendation.py in later milestones); there is still no scheduler
distinguishing a 20:00 preview from the 05:30 final decision (scheduler.py,
also a later milestone) - `_async_update_data` simply reflects "as of now".
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ALTITUDE,
    CONF_ANEMOMETER_HEIGHT,
    DATA_QUALITY_INITIALIZING,
    DOMAIN,
)
from .et0 import compute_et0
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
        """Compute ET0 for the current day from the live weather snapshot.

        No per-zone balance/recommendation yet: this only reflects "as of
        now" and is recomputed whenever the coordinator refreshes (there is
        no scheduler-driven 20:00 preview / 05:30 final distinction yet).
        """
        et0_result = compute_et0(
            self.weather.today_snapshot(),
            latitude_deg=self.hass.config.latitude,
            altitude_m=float(self.entry.data[CONF_ALTITUDE]),
            anemometer_height_m=float(self.entry.data[CONF_ANEMOMETER_HEIGHT]),
        )
        return {"data_quality": DATA_QUALITY_INITIALIZING, "et0": et0_result}
