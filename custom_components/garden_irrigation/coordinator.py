"""Coordinator for garden_irrigation.

Milestone 2 added the WeatherAggregator (accumulators + persistence + a
bounded recorder backfill), owned here as `coordinator.weather`. Milestone 3
added ET0 computation for the current (in-progress) day from that
aggregator's live snapshot, exposed as `coordinator.data["et0"]`. Milestone 4
adds the per-zone water balance (`coordinator.balance`, `coordinator.data
["balance"]`): whenever a finalized (completed, midnight-rolled) weather
snapshot for "yesterday" becomes available, the balance for that day is
applied once per zone (idempotent - see balance.py). Milestone 6 adds the
manual-cycle event log and its `record_irrigation` service
(`coordinator.irrigation_log`, `coordinator.data["irrigation"]` per-zone/
per-source aggregates) - recording a cycle feeds directly into
`coordinator.balance`'s own ledger (used both by the once-daily deficit
calculation and by the existing irrigation_7d sensor), so no separate
deficit-update path is needed here. Milestone 7 adds the recommendation
engine (`coordinator.recommendation`, `coordinator.data["recommendation"]`:
a `{final, preview}` bundle per zone - see recommendation.py for why both are
always recomputed on every refresh) and the scheduler
(`coordinator.scheduler`), which only guarantees a refresh happens at 20:00
and 05:30 local time - it does not gate what gets computed, since the
final/preview distinction and the once-per-day balance idempotency already
make every refresh safe regardless of what triggered it. The notification
system (Telegram/persistent_notification, morning report, cycle-recorded
confirmations, and the notify-only monitor advisories) has been removed
entirely; `scheduler.py`'s periodic tick and `repairs.py` still surface
stale weather/WH51 data as Repair issues. Milestone 9 adds the operational state
(`coordinator.mode`, `coordinator.cycle_zone`/`cycle_started_at`/
`selected_cycle_zone`) behind its own store (STORAGE_KEY_OPERATIONAL) -
select.py/button.py/binary_sensor.py read and mutate it through the small
`async_set_mode`/`async_set_selected_cycle_zone`/`async_start_cycle`/
`async_end_cycle` methods below, and `async_update_listeners()` pushes the
change to those entities immediately without a full data refresh. None of
this touches balance/recommendation/irrigation_log's own state: the declared
cycle is purely informational until the user records it for real via the
existing `record_irrigation` service/backend.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import repairs
from .balance import BalanceEngine, ZoneBalanceResult
from .const import (
    CONF_ALTITUDE,
    CONF_ANEMOMETER_HEIGHT,
    DATA_QUALITY_INITIALIZING,
    DOMAIN,
    MODE_CALIBRATION,
    STORAGE_KEY_OPERATIONAL,
    ZONE_1,
    ZONES,
)
from .et0 import compute_et0
from .irrigation_log import IrrigationAggregate, IrrigationLog
from .recommendation import RecommendationEngine, ZoneRecommendationBundle
from .scheduler import Scheduler
from .storage import GardenIrrigationStore
from .weather import WeatherAggregator

_LOGGER = logging.getLogger(__name__)


class GardenIrrigationCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Event-driven coordinator (no polling: update_interval is None).

    Refreshes are triggered by state-change listeners (weather/WH51 entities)
    and by the 20:00/05:30 scheduler triggers - never by a fixed interval.
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
        self.irrigation_log = IrrigationLog(hass, entry, self)
        self.recommendation = RecommendationEngine(
            hass, entry, self.balance, self.irrigation_log
        )
        self.scheduler = Scheduler(hass, self)

        # Milestone 9: operational state (select.mode + the declared cycle).
        # Purely informational/UX - see async_start_cycle/async_end_cycle.
        self._operational_store = GardenIrrigationStore(hass, STORAGE_KEY_OPERATIONAL)
        self.mode: str = MODE_CALIBRATION
        self.selected_cycle_zone: str = ZONE_1
        self.cycle_zone: str | None = None
        self.cycle_started_at: datetime | None = None

    async def async_setup(self) -> None:
        """Start the weather listeners, restore the balance, register the
        record_irrigation service, restore the WH51 baseline, restore the
        operational state, and start the 20:00/05:30 scheduler triggers."""
        await self.weather.async_setup()
        await self.balance.async_setup()
        await self.irrigation_log.async_setup()
        await self.recommendation.async_setup()
        await self._async_restore_operational_state()
        await self.scheduler.async_setup()

    async def _async_restore_operational_state(self) -> None:
        stored = await self._operational_store.async_load()
        self.mode = stored.get("mode", MODE_CALIBRATION)
        self.selected_cycle_zone = stored.get("selected_cycle_zone", ZONE_1)
        self.cycle_zone = stored.get("cycle_zone")
        started_at_raw = stored.get("cycle_started_at")
        self.cycle_started_at = (
            dt_util.parse_datetime(started_at_raw) if started_at_raw else None
        )

    def _operational_save_data(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "selected_cycle_zone": self.selected_cycle_zone,
            "cycle_zone": self.cycle_zone,
            "cycle_started_at": (
                self.cycle_started_at.isoformat() if self.cycle_started_at else None
            ),
        }

    async def async_set_mode(self, mode: str) -> None:
        """Set the operational mode (calibration/monitoring) - UX/status only,
        never alters balance/recommendation/log data retroactively."""
        self.mode = mode
        await self._operational_store.async_save(self._operational_save_data())
        self.async_update_listeners()

    async def async_set_selected_cycle_zone(self, zone_id: str) -> None:
        """Set which zone `async_start_cycle` will target next."""
        self.selected_cycle_zone = zone_id
        await self._operational_store.async_save(self._operational_save_data())
        self.async_update_listeners()

    async def async_start_cycle(self) -> None:
        """Declare a manual cycle active for `selected_cycle_zone`, now.

        Purely declarative: no side effect on the deficit/irrigation log
        until the user actually records the cycle via the existing
        `record_irrigation` service/backend (irrigation_log.py, unchanged).
        """
        self.cycle_zone = self.selected_cycle_zone
        self.cycle_started_at = dt_util.now()
        await self._operational_store.async_save(self._operational_save_data())
        self.async_update_listeners()

    async def async_end_cycle(self) -> None:
        """Clear the declared-active-cycle state."""
        self.cycle_zone = None
        self.cycle_started_at = None
        await self._operational_store.async_save(self._operational_save_data())
        self.async_update_listeners()

    async def async_shutdown(self) -> None:
        """Stop the weather aggregator's listeners and force a final flush.

        Extends (not replaces) DataUpdateCoordinator.async_shutdown, which
        also cancels the coordinator's own scheduled refresh/debouncer.
        """
        await self.scheduler.async_shutdown()
        repairs.async_clear_all_issues(self.hass)
        await self.weather.async_shutdown()
        await self.balance.async_shutdown()
        await self.irrigation_log.async_shutdown()
        await self.recommendation.async_shutdown()
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

        irrigation_totals: dict[str, dict[str, IrrigationAggregate]] = {
            zone_id: self.irrigation_log.totals_by_source(zone_id) for zone_id in ZONES
        }

        now = dt_util.now()
        today_et0_mm = None if et0_result.incomplete else et0_result.et0_mm
        today_rain_mm = self.weather.today_snapshot().rain_mm
        recommendations: dict[str, ZoneRecommendationBundle] = {
            zone_id: self.recommendation.build(
                zone_id, balance_results[zone_id], today_et0_mm, today_rain_mm, now
            )
            for zone_id in ZONES
        }

        return {
            "data_quality": DATA_QUALITY_INITIALIZING,
            "et0": et0_result,
            "balance": balance_results,
            "irrigation": irrigation_totals,
            "recommendation": recommendations,
        }
