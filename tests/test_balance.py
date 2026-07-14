"""Tests for the garden_irrigation per-zone water balance engine (Milestone 4)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.balance import (
    SKIPPED_ALREADY_PROCESSED,
    SKIPPED_ET0_UNAVAILABLE,
    BalanceEngine,
    ZoneAgronomyParams,
)
from custom_components.garden_irrigation.const import DOMAIN, ZONE_1, ZONE_2, ZONES
from custom_components.garden_irrigation.coordinator import GardenIrrigationCoordinator

from .const import (
    rain_step_input,
    setup_mock_weather_states,
    soil_step_input,
    telegram_step_input,
    user_step_input,
    zones_step_input,
)

# CLAUDE.md defaults: Kc=0.95, root_depth=150mm, AWC=200mm/m -> TAW=30mm,
# p=0.5 -> RAW=15mm, rain_effective_factor=0.8, weekly cap=30mm.
TAW_MM = 30.0
RAW_MM = 15.0


def _full_entry_data() -> dict[str, Any]:
    return {
        **user_step_input(),
        **rain_step_input(),
        **soil_step_input(),
        **zones_step_input(),
        **telegram_step_input(),
    }


def _engine(hass: HomeAssistant) -> BalanceEngine:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    return BalanceEngine(hass, entry)


# ---------------------------------------------------------------------------
# ZoneAgronomyParams: TAW/RAW derivation
# ---------------------------------------------------------------------------


def test_zone_agronomy_params_taw_raw() -> None:
    params = ZoneAgronomyParams()
    assert params.taw_mm == TAW_MM
    assert params.raw_mm == RAW_MM


# ---------------------------------------------------------------------------
# Core daily balance formula: ETc, effective rain, deficit
# ---------------------------------------------------------------------------


async def test_first_day_no_rain_no_irrigation_accumulates_full_etc(
    hass: HomeAssistant,
) -> None:
    engine = _engine(hass)
    day = date(2026, 6, 1)

    result = engine.process_daily_balance(ZONE_1, day, et0_mm=5.0, rain_mm=0.0)

    assert result.applied is True
    assert result.skipped_reason is None
    assert result.etc_mm == 5.0 * 0.95
    assert result.eff_rain_mm == 0.0
    assert result.irrigation_mm == 0.0
    assert result.deficit_mm == 5.0 * 0.95
    assert engine.current_deficit_mm(ZONE_1) == result.deficit_mm


async def test_effective_rain_scarce_rain_uses_full_factor(hass: HomeAssistant) -> None:
    """Rain well below (deficit+ETc): eff_rain = rain * factor, not capped."""
    engine = _engine(hass)
    day = date(2026, 6, 1)

    result = engine.process_daily_balance(ZONE_1, day, et0_mm=5.0, rain_mm=2.0)

    etc = 5.0 * 0.95
    expected_eff_rain = 2.0 * 0.8
    assert expected_eff_rain < etc  # sanity: rain is indeed the scarce case
    assert result.eff_rain_mm == expected_eff_rain
    assert result.deficit_mm == etc - expected_eff_rain


async def test_effective_rain_abundant_rain_capped_at_deficit_plus_etc(
    hass: HomeAssistant,
) -> None:
    """Heavy rain: eff_rain capped at (prev_deficit + ETc), never "banked" beyond it."""
    engine = _engine(hass)
    day = date(2026, 6, 1)

    result = engine.process_daily_balance(ZONE_1, day, et0_mm=5.0, rain_mm=100.0)

    etc = 5.0 * 0.95
    assert result.eff_rain_mm == etc  # capped at prev_deficit(0) + etc
    assert result.deficit_mm == 0.0


async def test_deficit_never_goes_below_zero(hass: HomeAssistant) -> None:
    """Irrigation larger than the day's remaining need clamps deficit at 0."""
    engine = _engine(hass)
    day = date(2026, 6, 1)
    engine.record_irrigation(ZONE_1, datetime(2026, 6, 1, 12, tzinfo=UTC), mm=50.0)

    result = engine.process_daily_balance(ZONE_1, day, et0_mm=5.0, rain_mm=0.0)

    assert result.irrigation_mm == 50.0
    assert result.deficit_mm == 0.0


async def test_deficit_clamped_at_taw(hass: HomeAssistant) -> None:
    """A single very dry day cannot push the deficit past TAW."""
    engine = _engine(hass)
    day = date(2026, 6, 1)

    result = engine.process_daily_balance(ZONE_1, day, et0_mm=100.0, rain_mm=0.0)

    assert result.deficit_mm == TAW_MM


# ---------------------------------------------------------------------------
# Multi-day sequences
# ---------------------------------------------------------------------------


async def test_multi_day_sequence_accumulates_and_zones_are_independent(
    hass: HomeAssistant,
) -> None:
    engine = _engine(hass)
    day1 = date(2026, 6, 1)
    day2 = date(2026, 6, 2)
    day3 = date(2026, 6, 3)

    r1 = engine.process_daily_balance(ZONE_1, day1, et0_mm=5.0, rain_mm=0.0)
    r2 = engine.process_daily_balance(ZONE_1, day2, et0_mm=5.0, rain_mm=0.0)
    r3 = engine.process_daily_balance(ZONE_1, day3, et0_mm=5.0, rain_mm=1.0)

    etc = 5.0 * 0.95
    assert r1.deficit_mm == etc
    assert r2.deficit_mm == etc * 2
    expected_eff_rain_day3 = min(1.0 * 0.8, r2.deficit_mm + etc)
    assert r3.deficit_mm == r2.deficit_mm + etc - expected_eff_rain_day3

    # Zone 2 was never processed: independent state, still at zero.
    assert engine.current_deficit_mm(ZONE_2) == 0.0


# ---------------------------------------------------------------------------
# Idempotency / double-processing protection
# ---------------------------------------------------------------------------


async def test_double_processing_same_day_is_ignored(hass: HomeAssistant) -> None:
    engine = _engine(hass)
    day = date(2026, 6, 1)

    first = engine.process_daily_balance(ZONE_1, day, et0_mm=5.0, rain_mm=0.0)
    # Second call for the same day, even with different inputs, must be a
    # no-op: it must not re-derive the deficit from these different values.
    second = engine.process_daily_balance(ZONE_1, day, et0_mm=999.0, rain_mm=0.0)

    assert first.applied is True
    assert second.applied is False
    assert second.skipped_reason == SKIPPED_ALREADY_PROCESSED
    assert second.deficit_mm == first.deficit_mm
    assert engine.current_deficit_mm(ZONE_1) == first.deficit_mm


async def test_et0_unavailable_leaves_deficit_unchanged_and_day_not_marked_processed(
    hass: HomeAssistant,
) -> None:
    engine = _engine(hass)
    day = date(2026, 6, 1)
    engine.process_daily_balance(ZONE_1, day, et0_mm=5.0, rain_mm=0.0)
    deficit_after_day1 = engine.current_deficit_mm(ZONE_1)

    next_day = date(2026, 6, 2)
    result = engine.process_daily_balance(ZONE_1, next_day, et0_mm=None, rain_mm=0.0)

    assert result.applied is False
    assert result.skipped_reason == SKIPPED_ET0_UNAVAILABLE
    assert result.deficit_mm == deficit_after_day1
    assert engine.current_deficit_mm(ZONE_1) == deficit_after_day1

    # Since the day was NOT marked processed, better data arriving later can
    # still be applied for that same day.
    retried = engine.process_daily_balance(ZONE_1, next_day, et0_mm=5.0, rain_mm=0.0)
    assert retried.applied is True


# ---------------------------------------------------------------------------
# Weekly rolling (sliding 7x24h) recorded-irrigation cap
# ---------------------------------------------------------------------------


async def test_weekly_irrigation_sum_and_cap_reached(
    hass: HomeAssistant, freezer: Any
) -> None:
    engine = _engine(hass)
    as_of = datetime(2026, 6, 8, 6, 0, tzinfo=UTC)
    engine.record_irrigation(ZONE_1, datetime(2026, 6, 3, 8, 0, tzinfo=UTC), mm=15.0)
    engine.record_irrigation(ZONE_1, datetime(2026, 6, 6, 8, 0, tzinfo=UTC), mm=15.0)

    assert engine.weekly_irrigation_mm(ZONE_1, as_of) == 30.0

    # process_daily_balance always applies the *completed* day (`day`), but
    # the weekly cap it reports is anchored to "now" (see
    # weekly_irrigation_mm's docstring) - freeze "now" to as_of so this test
    # exercises that anchor explicitly instead of coincidentally matching it.
    freezer.move_to(as_of)
    day = as_of.date()
    result = engine.process_daily_balance(ZONE_1, day, et0_mm=1.0, rain_mm=0.0)
    assert result.irrigation_7d_mm == 30.0
    assert result.weekly_cap_reached is True


async def test_weekly_window_excludes_records_older_than_seven_days(
    hass: HomeAssistant,
) -> None:
    engine = _engine(hass)
    old_ts = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    engine.record_irrigation(ZONE_1, old_ts, mm=10.0)

    as_of = old_ts + timedelta(days=7, hours=1)
    assert engine.weekly_irrigation_mm(ZONE_1, as_of) == 0.0


async def test_weekly_cap_not_reached_below_threshold(
    hass: HomeAssistant, freezer: Any
) -> None:
    engine = _engine(hass)
    as_of = datetime(2026, 6, 8, 6, 0, tzinfo=UTC)
    engine.record_irrigation(ZONE_1, datetime(2026, 6, 6, 8, 0, tzinfo=UTC), mm=10.0)

    freezer.move_to(as_of)
    day = as_of.date()
    result = engine.process_daily_balance(ZONE_1, day, et0_mm=1.0, rain_mm=0.0)

    assert result.irrigation_7d_mm == 10.0
    assert result.weekly_cap_reached is False


async def test_weekly_cap_reflects_irrigation_recorded_after_the_processed_day(
    hass: HomeAssistant, freezer: Any
) -> None:
    """Regression: the production coordinator always applies `day = yesterday`
    (coordinator.py), while a cycle can be recorded at any later instant
    (today). The weekly cap must reflect that recording immediately, not
    only after `day` itself advances to include it at the next 05:30
    rollover."""
    engine = _engine(hass)
    yesterday = date(2026, 6, 7)
    now = datetime(2026, 6, 8, 9, 0, tzinfo=UTC)
    freezer.move_to(now)

    # Applying "yesterday"'s balance first, as the real coordinator does -
    # with no irrigation recorded yet.
    result_before = engine.process_daily_balance(
        ZONE_1, yesterday, et0_mm=1.0, rain_mm=0.0
    )
    assert result_before.irrigation_7d_mm == 0.0

    # A cycle is now recorded "today" (after yesterday already ended).
    engine.record_irrigation(ZONE_1, now, mm=12.0)

    # Reporting current state again (e.g. the next coordinator refresh,
    # still before the next day's finalization) must already reflect it,
    # even though `day` itself (yesterday) hasn't changed.
    pending = engine.pending_result(ZONE_1, yesterday)
    assert pending.irrigation_7d_mm == 12.0


# ---------------------------------------------------------------------------
# pending_result: reporting without processing, no warning-worthy state change
# ---------------------------------------------------------------------------


async def test_pending_result_does_not_mutate_state(hass: HomeAssistant) -> None:
    engine = _engine(hass)
    day = date(2026, 6, 1)

    pending = engine.pending_result(ZONE_1, day)

    assert pending.applied is False
    assert pending.skipped_reason is None
    assert pending.deficit_mm == 0.0
    # No last_balance_date was set, so a real call for the same day still runs.
    result = engine.process_daily_balance(ZONE_1, day, et0_mm=5.0, rain_mm=0.0)
    assert result.applied is True


# ---------------------------------------------------------------------------
# Persistence: restart-safe deficit/last_balance_date/irrigation ledger
# ---------------------------------------------------------------------------


async def test_state_survives_setup_shutdown_roundtrip(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    engine1 = BalanceEngine(hass, entry)
    await engine1.async_setup()
    day = date(2026, 6, 1)
    engine1.process_daily_balance(ZONE_1, day, et0_mm=5.0, rain_mm=0.0)
    engine1.record_irrigation(ZONE_1, datetime(2026, 6, 1, 12, tzinfo=UTC), mm=3.0)
    await engine1.async_shutdown()

    engine2 = BalanceEngine(hass, entry)
    await engine2.async_setup()

    assert engine2.current_deficit_mm(ZONE_1) == engine1.current_deficit_mm(ZONE_1)
    # Same day re-processing on the restarted engine is still a no-op.
    replay = engine2.process_daily_balance(ZONE_1, day, et0_mm=999.0, rain_mm=0.0)
    assert replay.applied is False
    assert replay.skipped_reason == SKIPPED_ALREADY_PROCESSED
    # The irrigation ledger (needed for the rolling cap) survived too.
    as_of = datetime(2026, 6, 1, 23, 59, tzinfo=UTC)
    assert engine2.weekly_irrigation_mm(ZONE_1, as_of) == 3.0


# ---------------------------------------------------------------------------
# Minimal coordinator integration
# ---------------------------------------------------------------------------


async def test_coordinator_exposes_pending_balance_before_any_finalized_day(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator = GardenIrrigationCoordinator(hass, entry)

    await coordinator.async_refresh()

    assert coordinator.data is not None
    balance = coordinator.data["balance"]
    assert set(balance) == set(ZONES)
    for zone_id in ZONES:
        assert balance[zone_id].applied is False
        assert balance[zone_id].deficit_mm == 0.0


async def test_coordinator_applies_balance_once_finalized_weather_is_available(
    hass: HomeAssistant, freezer: Any
) -> None:
    """End-to-end: a finalized "yesterday" weather snapshot feeds ET0 and the
    balance is applied for that day through the coordinator."""
    await hass.config.async_set_time_zone("UTC")
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    start = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    freezer.move_to(start)

    coordinator = GardenIrrigationCoordinator(hass, entry)
    await coordinator.async_setup()
    try:
        # States must be set AFTER the weather listener is registered so the
        # accumulators actually observe them via state_changed events (a
        # pre-existing state at setup time produces no such event).
        setup_mock_weather_states(hass)
        await hass.async_block_till_done()

        midnight = datetime(2026, 6, 2, 0, 0, tzinfo=UTC)
        await coordinator.weather._handle_midnight(midnight)
        freezer.move_to(midnight + timedelta(hours=6))

        await coordinator.async_refresh()

        balance = coordinator.data["balance"]
        for zone_id in ZONES:
            assert balance[zone_id].day == date(2026, 6, 1)
            assert balance[zone_id].applied is True
            assert balance[zone_id].deficit_mm is not None
            assert balance[zone_id].deficit_mm > 0.0
    finally:
        await coordinator.async_shutdown()
