"""Coordinator for garden_irrigation.

Milestone 2 added the WeatherAggregator (accumulators + persistence + a
bounded recorder backfill), owned here as `coordinator.weather`. Milestone 3
added ET0 computation for the current (in-progress) day from that
aggregator's live snapshot, exposed as `coordinator.data["et0"]`. Milestone 4
adds the per-zone water balance (`coordinator.balance`, `coordinator.data
["balance"]`): whenever a finalized (completed, midnight-rolled) weather
snapshot for "yesterday" becomes available, the balance for that day is
applied once per zone (idempotent - see balance.py). There is still no
scheduler distinguishing a 20:00 preview from the 05:30 final decision
(scheduler.py, a later milestone) - `_async_update_data` simply applies the
balance for the most recently completed day as soon as its weather data is
available, whenever the coordinator happens to refresh. The recommendation
engine is NOT started here (see recommendation.py in a later milestone).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .balance import BalanceEngine, ZoneBalanceResult
from .const import (
    CONF_ALTITUDE,
    CONF_ANEMOMETER_HEIGHT,
    DATA_QUALITY_INITIALIZING,
    DOMAIN,
    ZONES,
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
        self.balance = BalanceEngine(hass, entry)

    async def async_setup(self) -> None:
        """Start the weather aggregator's listeners and restore the balance state."""
        await self.weather.async_setup()
        await self.balance.async_setup()

    async def async_shutdown(self) -> None:
        """Stop the weather aggregator's listeners and force a final flush.

        Extends (not replaces) DataUpdateCoordinator.async_shutdown, which
        also cancels the coordinator's own scheduled refresh/debouncer.
        """
        await self.weather.async_shutdown()
        await self.balance.async_shutdown()
        await super().async_shutdown()

    async def _async_update_data(self) -> dict[str, Any]:
        """Compute ET0 for the current day and apply the balance for "yesterday".

        ET0 reflects "as of now" for the still-in-progress day, recomputed on
        every refresh. The water balance for the most recently completed
        local day is applied once it has a finalized weather snapshot (see
        WeatherAggregator.get_finalized_day) - applying it is idempotent, so
        repeated refreshes before or after that data appears are harmless.
        """
        et0_result = compute_et0(
            self.weather.today_snapshot(),
            latitude_deg=self.hass.config.latitude,
            altitude_m=float(self.entry.data[CONF_ALTITUDE]),
            anemometer_height_m=float(self.entry.data[CONF_ANEMOMETER_HEIGHT]),
        )

        yesterday = dt_util.now().date() - timedelta(days=1)
        finalized_yesterday = self.weather.get_finalized_day(yesterday)
        yesterday_et0_mm: float | None = None
        if finalized_yesterday is not None:
            yesterday_et0 = compute_et0(
                finalized_yesterday,
                latitude_deg=self.hass.config.latitude,
                altitude_m=float(self.entry.data[CONF_ALTITUDE]),
                anemometer_height_m=float(self.entry.data[CONF_ANEMOMETER_HEIGHT]),
            )
            yesterday_et0_mm = (
                None if yesterday_et0.incomplete else yesterday_et0.et0_mm
            )

        balance_results: dict[str, ZoneBalanceResult] = {}
        for zone_id in ZONES:
            if finalized_yesterday is not None:
                balance_results[zone_id] = self.balance.process_daily_balance(
                    zone_id, yesterday, yesterday_et0_mm, finalized_yesterday.rain_mm
                )
            else:
                balance_results[zone_id] = self.balance.pending_result(
                    zone_id, yesterday
                )

        return {
            "data_quality": DATA_QUALITY_INITIALIZING,
            "et0": et0_result,
            "balance": balance_results,
        }
