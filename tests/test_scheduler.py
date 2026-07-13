"""Tests for the garden_irrigation scheduler (Milestones 7 and 8)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.garden_irrigation.const import (
    DEFAULT_STALE_WEATHER_ERROR_HOURS,
    DEFAULT_STALE_WEATHER_WARNING_MINUTES,
    DEFAULT_STALE_WH51_ERROR_HOURS,
    DEFAULT_STALE_WH51_WARNING_HOURS,
    DEFAULT_WH51_BATTERY_WARNING_PERCENT,
    DEFAULT_WH51_SIGNAL_WARNING,
    DEFAULT_WIND_WARNING_AVG_KMH,
    DEFAULT_WIND_WARNING_GUST_KMH,
    DOMAIN,
    ZONE_1,
    ZONE_2,
)
from custom_components.garden_irrigation.coordinator import GardenIrrigationCoordinator
from custom_components.garden_irrigation.weather import DailyWeatherSnapshot

from .const import (
    MOCK_HUMIDITY_ENTITY,
    MOCK_PRESSURE_ENTITY,
    MOCK_RAIN_RATE_ENTITY,
    MOCK_SOLAR_RADIATION_ENTITY,
    MOCK_TEMPERATURE_ENTITY,
    MOCK_WIND_SPEED_ENTITY,
    MOCK_ZONE1_BATTERY_ENTITY,
    MOCK_ZONE1_SIGNAL_ENTITY,
    MOCK_ZONE1_SOIL_ENTITY,
    MOCK_ZONE2_SOIL_ENTITY,
    rain_step_input,
    setup_mock_weather_states,
    soil_step_input,
    telegram_step_input,
    user_step_input,
    zones_step_input,
)


def _refresh_baseline_except_zone1_soil(hass: HomeAssistant) -> None:
    """Re-set every mandatory monitor entity except zone_1's WH51 sensor, so
    it alone can be driven into staleness while everything else stays fresh.

    `force_update=True` is required: re-setting an entity to the SAME value
    it already has is a no-op for `last_updated` otherwise, which would let
    these "still fresh" entities silently go stale too.
    """
    for entity_id in (
        MOCK_TEMPERATURE_ENTITY,
        MOCK_HUMIDITY_ENTITY,
        MOCK_PRESSURE_ENTITY,
        MOCK_SOLAR_RADIATION_ENTITY,
        MOCK_WIND_SPEED_ENTITY,
        MOCK_ZONE2_SOIL_ENTITY,
    ):
        hass.states.async_set(entity_id, "1.0", {}, force_update=True)


def _full_entry_data(**overrides: Any) -> dict[str, Any]:
    return {
        **user_step_input(),
        **rain_step_input(),
        **soil_step_input(**overrides),
        **zones_step_input(),
        **telegram_step_input(),
    }


def _coordinator(hass: HomeAssistant, **overrides: Any) -> GardenIrrigationCoordinator:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data(**overrides))
    entry.add_to_hass(hass)
    return GardenIrrigationCoordinator(hass, entry)


def _issue(hass: HomeAssistant, issue_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, issue_id)


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


# ---------------------------------------------------------------------------
# Milestone 8: morning report content
# ---------------------------------------------------------------------------


async def test_morning_report_summarizes_each_zone(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    coordinator.data = {
        "recommendation": {
            "zone_1": SimpleNamespace(
                final=SimpleNamespace(
                    ready=True, needs_irrigation=True, recommended_mm=12.5
                )
            ),
            "zone_2": SimpleNamespace(
                final=SimpleNamespace(
                    ready=True, needs_irrigation=False, recommended_mm=0.0
                )
            ),
        }
    }

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._send_morning_report()

    mock_send.assert_awaited_once()
    message = mock_send.await_args.args[0]
    assert "zone_1" in message
    assert "12.5" in message
    assert "zone_2" in message
    assert mock_send.await_args.kwargs["notification_id"] == "morning_report"


async def test_morning_report_handles_not_ready_zone(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    coordinator.data = {
        "recommendation": {
            "zone_1": SimpleNamespace(
                final=SimpleNamespace(
                    ready=False, needs_irrigation=None, recommended_mm=None
                )
            ),
        }
    }

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._send_morning_report()

    mock_send.assert_awaited_once()
    assert "zone_1" in mock_send.await_args.args[0]


async def test_morning_report_skipped_before_first_refresh(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)  # coordinator.data is still None

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._send_morning_report()

    mock_send.assert_not_awaited()


async def test_morning_report_skipped_when_no_zone_has_a_recommendation(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    coordinator.data = {"recommendation": {}}

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._send_morning_report()

    mock_send.assert_not_awaited()


# ---------------------------------------------------------------------------
# Milestone 8: WH51 stale monitor (3h warning / 12h error)
# ---------------------------------------------------------------------------


async def test_wh51_stale_warning_then_error_then_resolved(
    hass: HomeAssistant, freezer: Any
) -> None:
    start = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(start)
    coordinator = _coordinator(hass)
    # Fresh baseline for every other check (zone_2 WH51, all weather
    # entities) so only zone_1's WH51 staleness is under test here.
    setup_mock_weather_states(hass)

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        # Fresh: no advisory.
        await coordinator.scheduler._handle_monitor_tick(start)
        mock_send.assert_not_awaited()
        assert _issue(hass, "wh51_stale_zone_1") is None

        # Past the warning threshold, not yet the error one. Refresh every
        # other monitored entity so only zone_1's WH51 sensor looks stale.
        warning_time = start + timedelta(
            hours=DEFAULT_STALE_WH51_WARNING_HOURS, minutes=1
        )
        freezer.move_to(warning_time)
        _refresh_baseline_except_zone1_soil(hass)
        await coordinator.scheduler._handle_monitor_tick(warning_time)
        mock_send.assert_awaited_once()
        issue = _issue(hass, "wh51_stale_zone_1")
        assert issue is not None
        assert issue.severity == ir.IssueSeverity.WARNING

        # Still within the warning window: no repeat notification (dedup).
        still_warning = warning_time + timedelta(minutes=5)
        freezer.move_to(still_warning)
        _refresh_baseline_except_zone1_soil(hass)
        await coordinator.scheduler._handle_monitor_tick(still_warning)
        mock_send.assert_awaited_once()

        # Past the error threshold: a new (transition) notification.
        error_time = start + timedelta(hours=DEFAULT_STALE_WH51_ERROR_HOURS, minutes=1)
        freezer.move_to(error_time)
        _refresh_baseline_except_zone1_soil(hass)
        await coordinator.scheduler._handle_monitor_tick(error_time)
        assert mock_send.await_count == 2
        issue = _issue(hass, "wh51_stale_zone_1")
        assert issue is not None
        assert issue.severity == ir.IssueSeverity.ERROR

        # Sensor updates again: resolved, repair cleared (no extra notify).
        hass.states.async_set(
            MOCK_ZONE1_SOIL_ENTITY, "46", {"unit_of_measurement": "%"}
        )
        _refresh_baseline_except_zone1_soil(hass)
        await coordinator.scheduler._handle_monitor_tick(error_time)
        assert mock_send.await_count == 2
        assert _issue(hass, "wh51_stale_zone_1") is None


async def test_wh51_missing_entity_is_treated_as_error(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    setup_mock_weather_states(hass)  # fresh baseline for everything else
    hass.states.async_remove(MOCK_ZONE1_SOIL_ENTITY)  # then remove just this one

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._handle_monitor_tick(
            datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
        )

    mock_send.assert_awaited_once()
    issue = _issue(hass, "wh51_stale_zone_1")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR


# ---------------------------------------------------------------------------
# Milestone 8: weather stale monitor (30min warning / 2h error)
# ---------------------------------------------------------------------------


async def test_weather_stale_warning_and_error(
    hass: HomeAssistant, freezer: Any
) -> None:
    start = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(start)
    coordinator = _coordinator(hass)
    # Fresh baseline for both zones' WH51 entities so only the weather
    # entities' staleness is under test here. DEFAULT_STALE_WEATHER_ERROR_HOURS
    # (2h) stays comfortably below DEFAULT_STALE_WH51_WARNING_HOURS (3h), so
    # WH51 never crosses its own threshold during this test.
    setup_mock_weather_states(hass)

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._handle_monitor_tick(start)
        mock_send.assert_not_awaited()

        warning_time = start + timedelta(
            minutes=DEFAULT_STALE_WEATHER_WARNING_MINUTES + 1
        )
        freezer.move_to(warning_time)
        await coordinator.scheduler._handle_monitor_tick(warning_time)
        mock_send.assert_awaited_once()
        issue = _issue(hass, "weather_stale")
        assert issue is not None
        assert issue.severity == ir.IssueSeverity.WARNING

        error_time = start + timedelta(
            hours=DEFAULT_STALE_WEATHER_ERROR_HOURS, minutes=1
        )
        freezer.move_to(error_time)
        await coordinator.scheduler._handle_monitor_tick(error_time)
        assert mock_send.await_count == 2
        issue = _issue(hass, "weather_stale")
        assert issue is not None
        assert issue.severity == ir.IssueSeverity.ERROR

        # Weather entities update again: resolved, repair cleared silently.
        # force_update=True: setup_mock_weather_states() reuses the same
        # fixed values, which alone would not bump last_updated.
        for entity_id, value in (
            (MOCK_TEMPERATURE_ENTITY, "18.5"),
            (MOCK_HUMIDITY_ENTITY, "62"),
            (MOCK_PRESSURE_ENTITY, "1013.2"),
            (MOCK_SOLAR_RADIATION_ENTITY, "450"),
            (MOCK_WIND_SPEED_ENTITY, "8.5"),
        ):
            hass.states.async_set(entity_id, value, {}, force_update=True)
        await coordinator.scheduler._handle_monitor_tick(error_time)
        assert mock_send.await_count == 2
        assert _issue(hass, "weather_stale") is None


# ---------------------------------------------------------------------------
# Milestone 8: WH51 battery/signal advisories (notify-only, no repair)
# ---------------------------------------------------------------------------


async def test_wh51_battery_unavailable_is_ignored(hass: HomeAssistant) -> None:
    """An unavailable/unknown battery reading isn't treated as "low"."""
    coordinator = _coordinator(hass, zone1_battery_entity=MOCK_ZONE1_BATTERY_ENTITY)
    setup_mock_weather_states(hass)
    hass.states.async_set(MOCK_ZONE1_BATTERY_ENTITY, "unavailable", {})

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._handle_monitor_tick(
            datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
        )

    mock_send.assert_not_awaited()


async def test_wh51_battery_non_numeric_is_ignored(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass, zone1_battery_entity=MOCK_ZONE1_BATTERY_ENTITY)
    setup_mock_weather_states(hass)
    hass.states.async_set(MOCK_ZONE1_BATTERY_ENTITY, "not_a_number", {})

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._handle_monitor_tick(
            datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
        )

    mock_send.assert_not_awaited()


async def test_wh51_battery_low_notifies_without_repair(
    hass: HomeAssistant, freezer: Any
) -> None:
    now = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(now)
    coordinator = _coordinator(hass, zone1_battery_entity=MOCK_ZONE1_BATTERY_ENTITY)
    setup_mock_weather_states(hass)  # fresh baseline; battery overridden below
    hass.states.async_set(
        MOCK_ZONE1_BATTERY_ENTITY,
        str(DEFAULT_WH51_BATTERY_WARNING_PERCENT - 1),
        {"unit_of_measurement": "%"},
    )

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._handle_monitor_tick(now)

    mock_send.assert_awaited_once()
    assert _issue(hass, f"wh51_battery_{ZONE_1}") is None  # advisory-only, no repair


async def test_wh51_battery_ok_does_not_notify(
    hass: HomeAssistant, freezer: Any
) -> None:
    now = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(now)
    coordinator = _coordinator(hass, zone1_battery_entity=MOCK_ZONE1_BATTERY_ENTITY)
    setup_mock_weather_states(hass)
    hass.states.async_set(
        MOCK_ZONE1_BATTERY_ENTITY,
        str(DEFAULT_WH51_BATTERY_WARNING_PERCENT + 10),
        {"unit_of_measurement": "%"},
    )

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._handle_monitor_tick(now)

    mock_send.assert_not_awaited()


async def test_wh51_signal_low_notifies(hass: HomeAssistant, freezer: Any) -> None:
    now = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(now)
    coordinator = _coordinator(hass, zone1_signal_entity=MOCK_ZONE1_SIGNAL_ENTITY)
    setup_mock_weather_states(hass)
    hass.states.async_set(
        MOCK_ZONE1_SIGNAL_ENTITY, str(DEFAULT_WH51_SIGNAL_WARNING), {}
    )

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._handle_monitor_tick(now)

    mock_send.assert_awaited_once()


async def test_battery_signal_not_configured_are_skipped(
    hass: HomeAssistant, freezer: Any
) -> None:
    now = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(now)
    coordinator = _coordinator(hass)  # neither battery nor signal entity configured
    setup_mock_weather_states(hass)

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._handle_monitor_tick(now)

    mock_send.assert_not_awaited()


# ---------------------------------------------------------------------------
# Milestone 8: wind monitor (avg 15 km/h / gust 25 km/h)
# ---------------------------------------------------------------------------


async def test_strong_wind_notifies(hass: HomeAssistant, freezer: Any) -> None:
    now = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(now)
    coordinator = _coordinator(hass)
    setup_mock_weather_states(hass)  # fresh WH51/weather baseline
    snapshot = DailyWeatherSnapshot(
        day=now.date(),
        temp_min=10.0,
        temp_max=20.0,
        temp_mean=15.0,
        rh_min=40.0,
        rh_max=80.0,
        rh_mean=60.0,
        pressure_mean=1013.0,
        wind_mean=DEFAULT_WIND_WARNING_AVG_KMH + 1,
        wind_gust_max=DEFAULT_WIND_WARNING_GUST_KMH + 1,
        solar_mj=15.0,
        rain_mm=0.0,
    )
    with (
        patch.object(coordinator.weather, "today_snapshot", return_value=snapshot),
        patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send,
    ):
        await coordinator.scheduler._handle_monitor_tick(now)

    mock_send.assert_awaited_once()
    message = mock_send.await_args.args[0]
    assert str(DEFAULT_WIND_WARNING_AVG_KMH + 1) in message


async def test_calm_wind_does_not_notify(hass: HomeAssistant, freezer: Any) -> None:
    now = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(now)
    coordinator = _coordinator(hass)
    setup_mock_weather_states(hass)
    snapshot = DailyWeatherSnapshot(
        day=now.date(),
        temp_min=10.0,
        temp_max=20.0,
        temp_mean=15.0,
        rh_min=40.0,
        rh_max=80.0,
        rh_mean=60.0,
        pressure_mean=1013.0,
        wind_mean=5.0,
        wind_gust_max=10.0,
        solar_mj=15.0,
        rain_mm=0.0,
    )
    with (
        patch.object(coordinator.weather, "today_snapshot", return_value=snapshot),
        patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send,
    ):
        await coordinator.scheduler._handle_monitor_tick(now)

    mock_send.assert_not_awaited()


# ---------------------------------------------------------------------------
# Milestone 8: monitor tick is registered/unsubscribed like the other triggers
# ---------------------------------------------------------------------------


async def test_async_setup_registers_monitor_tick(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    scheduler = coordinator.scheduler

    await scheduler.async_setup()
    try:
        assert scheduler._unsub_monitor is not None
    finally:
        await scheduler.async_shutdown()


async def test_async_shutdown_unsubscribes_monitor_tick(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    scheduler = coordinator.scheduler

    await scheduler.async_setup()
    await scheduler.async_shutdown()

    assert scheduler._unsub_monitor is None


# ---------------------------------------------------------------------------
# Milestone 9: rain-rate "stop advisory" while a cycle is declared active
# ---------------------------------------------------------------------------


async def test_no_rain_check_when_no_active_cycle(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    setup_mock_weather_states(hass)
    hass.states.async_set(MOCK_RAIN_RATE_ENTITY, "2.0", {"unit_of_measurement": "mm/h"})

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._handle_monitor_tick(
            datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
        )

    mock_send.assert_not_awaited()


async def test_rain_during_active_cycle_notifies(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    setup_mock_weather_states(hass)
    hass.states.async_set(MOCK_RAIN_RATE_ENTITY, "2.0", {"unit_of_measurement": "mm/h"})
    coordinator.cycle_zone = ZONE_1

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._handle_monitor_tick(
            datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
        )

    mock_send.assert_awaited_once()
    message = mock_send.await_args.args[0]
    assert ZONE_1 in message


async def test_dry_during_active_cycle_does_not_notify(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    setup_mock_weather_states(hass)
    hass.states.async_set(MOCK_RAIN_RATE_ENTITY, "0.0", {"unit_of_measurement": "mm/h"})
    coordinator.cycle_zone = ZONE_2

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._handle_monitor_tick(
            datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
        )

    mock_send.assert_not_awaited()


async def test_rain_during_cycle_dedup_no_repeat_while_still_raining(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    setup_mock_weather_states(hass)
    hass.states.async_set(MOCK_RAIN_RATE_ENTITY, "2.0", {"unit_of_measurement": "mm/h"})
    coordinator.cycle_zone = ZONE_1

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._handle_monitor_tick(
            datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
        )
        await coordinator.scheduler._handle_monitor_tick(
            datetime(2026, 6, 1, 8, 15, tzinfo=UTC)
        )

    mock_send.assert_awaited_once()


async def test_rain_during_cycle_resolves_silently_and_can_retrigger(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    setup_mock_weather_states(hass)
    hass.states.async_set(MOCK_RAIN_RATE_ENTITY, "2.0", {"unit_of_measurement": "mm/h"})
    coordinator.cycle_zone = ZONE_1

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._handle_monitor_tick(
            datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
        )
        assert mock_send.await_count == 1

        # Cycle ends: the next tick resolves the advisory silently.
        coordinator.cycle_zone = None
        await coordinator.scheduler._handle_monitor_tick(
            datetime(2026, 6, 1, 8, 15, tzinfo=UTC)
        )
        assert mock_send.await_count == 1

        # A new declared cycle while it's still raining notifies again.
        coordinator.cycle_zone = ZONE_2
        await coordinator.scheduler._handle_monitor_tick(
            datetime(2026, 6, 1, 8, 30, tzinfo=UTC)
        )
        assert mock_send.await_count == 2


async def test_rain_during_cycle_message_is_localized_to_italian(
    hass: HomeAssistant,
) -> None:
    hass.config.language = "it"
    coordinator = _coordinator(hass)
    setup_mock_weather_states(hass)
    hass.states.async_set(MOCK_RAIN_RATE_ENTITY, "2.0", {"unit_of_measurement": "mm/h"})
    coordinator.cycle_zone = ZONE_1

    with patch.object(coordinator.notifier, "async_send", new=AsyncMock()) as mock_send:
        await coordinator.scheduler._handle_monitor_tick(
            datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
        )

    mock_send.assert_awaited_once()
    message = mock_send.await_args.args[0]
    assert "piovendo" in message.lower()
