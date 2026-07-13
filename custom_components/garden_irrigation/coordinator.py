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
make every refresh safe regardless of what triggered it. Milestone 8 adds
the notifier (`coordinator.notifier`) and a minimal "cycle recorded"
confirmation: since irrigation_log.py itself is out of scope to touch, new
events are detected here by diffing `irrigation_log.events_for_zone()` ids
against the set seen as of the last refresh (seeded at startup so pre-
existing events are never re-notified) - irrigation_log.py's own semantics
are completely unchanged.
"""

from __future__ import annotations

import logging
from datetime import timedelta
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
    CONF_ZONE1_NAME,
    CONF_ZONE2_NAME,
    DATA_QUALITY_INITIALIZING,
    DEFAULT_ZONE1_NAME,
    DEFAULT_ZONE2_NAME,
    DOMAIN,
    ZONE_1,
    ZONES,
)
from .et0 import compute_et0
from .irrigation_log import IrrigationAggregate, IrrigationEvent, IrrigationLog
from .notify import TelegramNotifier, translate
from .recommendation import RecommendationEngine, ZoneRecommendationBundle
from .scheduler import Scheduler
from .weather import WeatherAggregator

_LOGGER = logging.getLogger(__name__)


def _zone_name(entry: ConfigEntry, zone_id: str) -> str:
    """Return the user-configured display name for `zone_id`.

    Re-implemented here (not imported from sensor.py/binary_sensor.py -
    private helpers, and both are out of scope to touch in M8).
    """
    if zone_id == ZONE_1:
        return str(entry.data.get(CONF_ZONE1_NAME, DEFAULT_ZONE1_NAME))
    return str(entry.data.get(CONF_ZONE2_NAME, DEFAULT_ZONE2_NAME))


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
        self.notifier = TelegramNotifier(hass, entry)
        self._notified_irrigation_event_ids: dict[str, set[str]] = {
            zone_id: set() for zone_id in ZONES
        }

    async def async_setup(self) -> None:
        """Start the weather listeners, restore the balance, register the
        record_irrigation service, restore the WH51 baseline, and start the
        20:00/05:30 scheduler triggers."""
        await self.weather.async_setup()
        await self.balance.async_setup()
        await self.irrigation_log.async_setup()
        await self.recommendation.async_setup()
        # Seed with events that already existed before startup, so restoring
        # a persisted event log never re-sends a "cycle recorded" confirmation.
        for zone_id in ZONES:
            self._notified_irrigation_event_ids[zone_id] = {
                event.id for event in self.irrigation_log.events_for_zone(zone_id)
            }
        await self.scheduler.async_setup()

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

        await self._notify_new_irrigation_events()

        return {
            "data_quality": DATA_QUALITY_INITIALIZING,
            "et0": et0_result,
            "balance": balance_results,
            "irrigation": irrigation_totals,
            "recommendation": recommendations,
        }

    async def _notify_new_irrigation_events(self) -> None:
        """Send a "cycle recorded" confirmation for any event not seen yet.

        Diffs `irrigation_log.events_for_zone()` against the ids already
        notified (seeded at startup - see async_setup) - irrigation_log.py
        itself is untouched and has no notify-on-record hook of its own.
        """
        for zone_id in ZONES:
            seen = self._notified_irrigation_event_ids[zone_id]
            for event in self.irrigation_log.events_for_zone(zone_id):
                if event.id in seen:
                    continue
                seen.add(event.id)
                await self._notify_cycle_recorded(zone_id, event)

    async def _notify_cycle_recorded(
        self, zone_id: str, event: IrrigationEvent
    ) -> None:
        zone_name = _zone_name(self.entry, zone_id)
        if event.mm is not None:
            message = translate(
                self.hass,
                "cycle_recorded",
                zone_id=zone_name,
                source=event.source,
                minutes=event.duration_minutes,
                mm=event.mm,
            )
        else:
            message = translate(
                self.hass,
                "cycle_recorded_uncalibrated",
                zone_id=zone_name,
                source=event.source,
                minutes=event.duration_minutes,
            )
        await self.notifier.async_send(
            message,
            title=translate(self.hass, "cycle_recorded_title"),
            notification_id=f"cycle_{event.id}",
        )
