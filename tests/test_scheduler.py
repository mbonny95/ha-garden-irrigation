"""Tests for the garden_irrigation scheduler (Milestone 7)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.garden_irrigation.const import DOMAIN
from custom_components.garden_irrigation.coordinator import GardenIrrigationCoordinator

from .const import (
    rain_step_input,
    soil_step_input,
    telegram_step_input,
    user_step_input,
    zones_step_input,
)


def _full_entry_data() -> dict[str, Any]:
    return {
        **user_step_input(),
        **rain_step_input(),
        **soil_step_input(),
        **zones_step_input(),
        **telegram_step_input(),
    }


def _coordinator(hass: HomeAssistant) -> GardenIrrigationCoordinator:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    return GardenIrrigationCoordinator(hass, entry)


# ---------------------------------------------------------------------------
# Setup/shutdown: listeners registered and cleanly unsubscribed
# ---------------------------------------------------------------------------


async def test_async_setup_registers_both_triggers(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    scheduler = coordinator.scheduler

    await scheduler.async_setup()
    try:
        assert scheduler._unsub_preview is not None
        assert scheduler._unsub_finalize is not None
    finally:
        await scheduler.async_shutdown()


async def test_async_shutdown_unsubscribes_both_triggers(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    scheduler = coordinator.scheduler

    await scheduler.async_setup()
    await scheduler.async_shutdown()

    assert scheduler._unsub_preview is None
    assert scheduler._unsub_finalize is None


# ---------------------------------------------------------------------------
# Handlers request a coordinator refresh (the final/preview distinction is
# entirely recommendation.py's - the scheduler only guarantees a refresh)
# ---------------------------------------------------------------------------


async def test_evening_preview_handler_requests_refresh(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    with patch.object(
        coordinator, "async_request_refresh", new=AsyncMock()
    ) as mock_refresh:
        await coordinator.scheduler._handle_evening_preview(
            datetime(2026, 6, 1, 20, 0, tzinfo=UTC)
        )
    mock_refresh.assert_awaited_once()


async def test_morning_finalize_handler_requests_refresh(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    with patch.object(
        coordinator, "async_request_refresh", new=AsyncMock()
    ) as mock_refresh:
        await coordinator.scheduler._handle_morning_finalize(
            datetime(2026, 6, 2, 5, 30, tzinfo=UTC)
        )
    mock_refresh.assert_awaited_once()


# ---------------------------------------------------------------------------
# Real time-tracking dispatch: triggers fire at the configured local times
# ---------------------------------------------------------------------------


async def test_triggers_fire_at_configured_local_times(
    hass: HomeAssistant, freezer: Any
) -> None:
    await hass.config.async_set_time_zone("UTC")
    coordinator = _coordinator(hass)
    # 10:00 start: both triggers' first occurrence is later that same day
    # (05:30 already "passed") or the next day, with no other alarm due in
    # between - see the DST test below for why this margin matters.
    start = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    freezer.move_to(start)

    with patch.object(
        coordinator, "async_request_refresh", new=AsyncMock()
    ) as mock_refresh:
        await coordinator.scheduler.async_setup()
        try:
            evening = datetime(2026, 6, 1, 20, 0, tzinfo=UTC)
            freezer.move_to(evening)
            async_fire_time_changed(hass, evening)
            await hass.async_block_till_done()
            assert mock_refresh.await_count == 1

            morning = datetime(2026, 6, 2, 5, 30, tzinfo=UTC)
            freezer.move_to(morning)
            async_fire_time_changed(hass, morning)
            await hass.async_block_till_done()
            assert mock_refresh.await_count == 2
        finally:
            await coordinator.scheduler.async_shutdown()


# ---------------------------------------------------------------------------
# DST transition: the trigger still fires exactly once per configured local
# time on both sides of a clock change - no double counting.
# ---------------------------------------------------------------------------


async def test_triggers_survive_dst_spring_forward(
    hass: HomeAssistant, freezer: Any
) -> None:
    """Europe/Rome: clocks jump 02:00 -> 03:00 on the last Sunday of March.

    2026's transition is on 2026-03-29. The 20:00/05:30 local triggers are
    well outside the 02:00-03:00 jump itself, so each must still fire exactly
    once per calendar day across the transition.
    """
    await hass.config.async_set_time_zone("Europe/Rome")
    rome = ZoneInfo("Europe/Rome")
    coordinator = _coordinator(hass)
    # 10:00 start, same reasoning as test_triggers_fire_at_configured_local_times:
    # both triggers' first occurrence lands later without an intervening alarm.
    freezer.move_to(datetime(2026, 3, 28, 10, 0, tzinfo=rome))

    with patch.object(
        coordinator, "async_request_refresh", new=AsyncMock()
    ) as mock_refresh:
        await coordinator.scheduler.async_setup()
        try:
            # Day before the DST transition (still CET, UTC+1): evening trigger.
            evening_before = datetime(2026, 3, 28, 20, 0, tzinfo=rome)
            freezer.move_to(evening_before)
            async_fire_time_changed(hass, evening_before)
            await hass.async_block_till_done()
            assert mock_refresh.await_count == 1

            # The transition morning itself (clocks already jumped 02:00 ->
            # 03:00 local at this point): the 05:30 finalize trigger.
            morning_of_transition = datetime(2026, 3, 29, 5, 30, tzinfo=rome)
            freezer.move_to(morning_of_transition)
            async_fire_time_changed(hass, morning_of_transition)
            await hass.async_block_till_done()
            assert mock_refresh.await_count == 2

            # Evening of the transition day (now CEST, UTC+2).
            evening_after = datetime(2026, 3, 29, 20, 0, tzinfo=rome)
            freezer.move_to(evening_after)
            async_fire_time_changed(hass, evening_after)
            await hass.async_block_till_done()
            assert mock_refresh.await_count == 3

            # The following morning: exactly one more firing, not two.
            morning_after = datetime(2026, 3, 30, 5, 30, tzinfo=rome)
            freezer.move_to(morning_after)
            async_fire_time_changed(hass, morning_after)
            await hass.async_block_till_done()
            assert mock_refresh.await_count == 4
        finally:
            await coordinator.scheduler.async_shutdown()
