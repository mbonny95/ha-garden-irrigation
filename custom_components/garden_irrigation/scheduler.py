"""Scheduler for garden_irrigation.

Milestone 7 scope only: two daily local-time triggers -
`DEFAULT_EVENING_CHECK_TIME` (20:00) and `DEFAULT_MORNING_CHECK_TIME` (05:30)
- that each simply request a coordinator refresh. Both the once-per-day
finalization of "yesterday" (balance.py, idempotent via `last_balance_date`)
and the always-recomputed, never-persisted "today so far" preview
(recommendation.py) already happen on EVERY coordinator refresh, regardless
of what triggered it (weather state changes, these two daily triggers, or a
manual refresh) - so this module does not need to special-case which
trigger fired to decide what to compute. Its only job is to GUARANTEE a
refresh happens close to those two wall-clock moments even if no other event
does, so that:
  - the preview seen around 20:00 reflects the day's weather up to that point;
  - the finalized deficit/recommendation seen shortly after 05:30 reflects
    the just-completed day (finalization can already have happened earlier
    too, e.g. via a weather state change right after midnight - this trigger
    is a safety net, not a gate; balance.py's idempotency guarantees the
    balance is never applied twice no matter how many refreshes happen).

`async_track_time_change` (also used by weather.py's midnight roll, not
modified here) handles DST transitions natively via wall-clock local time -
no special-casing is needed or added here.

No other periodic monitoring is added: the architecture is event-driven, not
polling (see CLAUDE.md), and staleness/wind/rain-during-cycle monitors are a
later milestone (scheduler.py monitors alongside notify.py, M8).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from .const import DEFAULT_EVENING_CHECK_TIME, DEFAULT_MORNING_CHECK_TIME

if TYPE_CHECKING:
    from .coordinator import GardenIrrigationCoordinator

_LOGGER = logging.getLogger(__name__)


def _parse_hms(value: str) -> tuple[int, int, int]:
    """Parse a "HH:MM:SS" const.py default into (hour, minute, second)."""
    hour_str, minute_str, second_str = value.split(":")
    return int(hour_str), int(minute_str), int(second_str)


class Scheduler:
    """Owns the two daily local-time coordinator-refresh triggers.

    Not an entity: plain domain logic held by the coordinator
    (`coordinator.scheduler`).
    """

    def __init__(
        self, hass: HomeAssistant, coordinator: GardenIrrigationCoordinator
    ) -> None:
        """Build the scheduler; no triggers are registered until async_setup."""
        self.hass = hass
        self._coordinator = coordinator
        self._unsub_preview: CALLBACK_TYPE | None = None
        self._unsub_finalize: CALLBACK_TYPE | None = None

    async def async_setup(self) -> None:
        """Register the 20:00 preview and 05:30 finalization triggers."""
        preview_hour, preview_minute, preview_second = _parse_hms(
            DEFAULT_EVENING_CHECK_TIME
        )
        finalize_hour, finalize_minute, finalize_second = _parse_hms(
            DEFAULT_MORNING_CHECK_TIME
        )
        self._unsub_preview = async_track_time_change(
            self.hass,
            self._handle_evening_preview,
            hour=preview_hour,
            minute=preview_minute,
            second=preview_second,
        )
        self._unsub_finalize = async_track_time_change(
            self.hass,
            self._handle_morning_finalize,
            hour=finalize_hour,
            minute=finalize_minute,
            second=finalize_second,
        )

    async def async_shutdown(self) -> None:
        """Unsubscribe both triggers."""
        if self._unsub_preview is not None:
            self._unsub_preview()
            self._unsub_preview = None
        if self._unsub_finalize is not None:
            self._unsub_finalize()
            self._unsub_finalize = None

    async def _handle_evening_preview(self, now: datetime) -> None:
        """20:00 local: guarantee a refresh so the preview reflects today so far."""
        await self._coordinator.async_request_refresh()

    async def _handle_morning_finalize(self, now: datetime) -> None:
        """05:30 local: guarantee a refresh so yesterday's balance finalizes."""
        await self._coordinator.async_request_refresh()
