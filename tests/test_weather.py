"""Tests for garden_irrigation weather aggregation (Milestone 2)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import DOMAIN
from custom_components.garden_irrigation.weather import (
    WeatherAggregator,
    _parse_float,
    _RainAccumulator,
    _TimeWeightedAccumulator,
)

from .const import (
    MOCK_DAILY_RAINFALL_ENTITY,
    MOCK_TEMPERATURE_ENTITY,
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


# ---------------------------------------------------------------------------
# _RainAccumulator: reset detection, no double counting, out-of-order/duplicate
# ---------------------------------------------------------------------------


def test_rain_first_sample_seeds_baseline_without_delta() -> None:
    acc = _RainAccumulator(reset_tolerance_mm=0.1)
    ts = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)

    acc.add_sample(3.0, ts)

    assert acc.daily_mm == 0.0
    assert acc.last_raw == 3.0


def test_rain_normal_accumulation() -> None:
    acc = _RainAccumulator(reset_tolerance_mm=0.1)
    t0 = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)

    acc.add_sample(3.0, t0)
    acc.add_sample(3.2, t0 + timedelta(minutes=10))
    acc.add_sample(4.0, t0 + timedelta(minutes=20))

    assert acc.daily_mm == pytest.approx(1.0)


def test_rain_small_decrement_is_noise_not_reset() -> None:
    acc = _RainAccumulator(reset_tolerance_mm=0.1)
    t0 = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)

    acc.add_sample(5.0, t0)
    acc.add_sample(5.2, t0 + timedelta(minutes=5))
    # Station wobble: 5.2 -> 5.15 is a 0.05mm decrement, within the 0.1mm tolerance.
    acc.add_sample(5.15, t0 + timedelta(minutes=10))

    assert acc.daily_mm == pytest.approx(0.2)  # unaffected by the wobble


def test_rain_reset_detected_beyond_tolerance() -> None:
    acc = _RainAccumulator(reset_tolerance_mm=0.1)
    t0 = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)

    acc.add_sample(8.0, t0)
    acc.add_sample(8.5, t0 + timedelta(minutes=5))
    # Station reset: drops to 0.3 (an 8.2mm decrement, far beyond tolerance).
    acc.add_sample(0.3, t0 + timedelta(minutes=10))

    assert acc.daily_mm == pytest.approx(0.5 + 0.3)


def test_rain_ignores_out_of_order_and_duplicate_timestamps() -> None:
    acc = _RainAccumulator(reset_tolerance_mm=0.1)
    t0 = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)

    acc.add_sample(1.0, t0)
    acc.add_sample(2.0, t0 + timedelta(minutes=10))
    assert acc.daily_mm == pytest.approx(1.0)

    # Out-of-order (earlier timestamp) update: must be ignored entirely.
    acc.add_sample(100.0, t0 + timedelta(minutes=5))
    assert acc.daily_mm == pytest.approx(1.0)
    assert acc.last_raw == 2.0

    # Duplicate timestamp (same ts as last processed): must also be ignored.
    acc.add_sample(50.0, t0 + timedelta(minutes=10))
    assert acc.daily_mm == pytest.approx(1.0)
    assert acc.last_raw == 2.0


def test_rain_finalize_and_reset_keeps_raw_baseline() -> None:
    acc = _RainAccumulator(reset_tolerance_mm=0.1)
    t0 = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)
    acc.add_sample(1.0, t0)
    acc.add_sample(2.5, t0 + timedelta(minutes=10))

    finalized = acc.finalize_and_reset()

    assert finalized == pytest.approx(1.5)
    assert acc.daily_mm == 0.0
    # The raw baseline survives the calendar-day reset: the physical station
    # counter is independent of our accounting boundary.
    assert acc.last_raw == 2.5
    assert acc.last_ts == t0 + timedelta(minutes=10)


def test_rain_no_double_counting_on_repeated_identical_values() -> None:
    """A sensor republishing the same value (heartbeat) must not add rain."""
    acc = _RainAccumulator(reset_tolerance_mm=0.1)
    t0 = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)

    acc.add_sample(2.0, t0)
    for minute in range(1, 6):
        acc.add_sample(2.0, t0 + timedelta(minutes=minute))

    assert acc.daily_mm == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _TimeWeightedAccumulator: min/max, weighted mean, integral, finalize/reset
# ---------------------------------------------------------------------------


def test_time_weighted_mean() -> None:
    acc = _TimeWeightedAccumulator()
    t0 = datetime(2026, 7, 13, 0, 0, tzinfo=UTC)
    acc.add_sample(10.0, t0)  # in effect 0h-1h
    acc.add_sample(20.0, t0 + timedelta(hours=1))  # in effect 1h-3h
    acc.add_sample(30.0, t0 + timedelta(hours=3))  # in effect from 3h

    as_of = t0 + timedelta(hours=4)

    # weighted: 10*1h + 20*2h + 30*1h = 10+40+30 = 80 over 4h => mean 20
    assert acc.mean_as_of(as_of) == pytest.approx(20.0)
    assert acc.minimum == 10.0
    assert acc.maximum == 30.0


def test_time_weighted_integral_for_solar_radiation() -> None:
    acc = _TimeWeightedAccumulator()
    t0 = datetime(2026, 7, 13, 8, 0, tzinfo=UTC)
    acc.add_sample(500.0, t0)  # W/m^2, constant for 2 hours

    as_of = t0 + timedelta(hours=2)

    # integral = 500 W/m2 * 7200s = 3,600,000 J/m2 = 3.6 MJ/m2
    assert acc.integral_mj_as_of(as_of) == pytest.approx(3.6)


def test_time_weighted_no_samples_returns_none() -> None:
    acc = _TimeWeightedAccumulator()
    as_of = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)

    assert acc.mean_as_of(as_of) is None
    assert acc.integral_mj_as_of(as_of) is None


def test_time_weighted_finalize_and_reset_carries_forward_last_value() -> None:
    acc = _TimeWeightedAccumulator()
    t0 = datetime(2026, 7, 13, 22, 0, tzinfo=UTC)
    acc.add_sample(15.0, t0)
    midnight = datetime(2026, 7, 14, 0, 0, tzinfo=UTC)

    finalized = acc.finalize_and_reset(midnight)

    # Closed interval: 15.0 in effect for 2 hours.
    assert finalized.mean == pytest.approx(15.0)
    assert finalized.minimum == 15.0
    assert finalized.maximum == 15.0
    # New day starts already "at" 15.0: the physical value doesn't reset at midnight.
    assert acc.minimum == 15.0
    assert acc.maximum == 15.0
    assert acc.weighted_sum == 0.0
    assert acc.total_seconds == 0.0
    assert acc.last_ts == midnight


def test_time_weighted_finalize_with_no_samples() -> None:
    acc = _TimeWeightedAccumulator()
    midnight = datetime(2026, 7, 14, 0, 0, tzinfo=UTC)

    finalized = acc.finalize_and_reset(midnight)

    assert finalized.mean is None
    assert finalized.minimum is None


# ---------------------------------------------------------------------------
# _parse_float: unknown/unavailable/invalid handling
# ---------------------------------------------------------------------------


def test_parse_float_rejects_unknown_unavailable_and_invalid() -> None:
    assert _parse_float(State("sensor.x", "unknown")) is None
    assert _parse_float(State("sensor.x", "unavailable")) is None
    assert _parse_float(State("sensor.x", "not_a_number")) is None
    assert _parse_float(State("sensor.x", "12.34")) == pytest.approx(12.34)


# ---------------------------------------------------------------------------
# WeatherAggregator: live listener wiring, persistence, midnight roll, backfill
# ---------------------------------------------------------------------------


async def test_live_updates_feed_accumulators(
    hass: HomeAssistant, freezer: Any
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    start = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)
    freezer.move_to(start)

    aggregator = WeatherAggregator(hass, entry)
    await aggregator.async_setup()
    try:
        hass.states.async_set(
            MOCK_TEMPERATURE_ENTITY, "10.0", {"unit_of_measurement": "°C"}
        )
        await hass.async_block_till_done()

        freezer.move_to(start + timedelta(hours=1))
        hass.states.async_set(
            MOCK_TEMPERATURE_ENTITY, "20.0", {"unit_of_measurement": "°C"}
        )
        await hass.async_block_till_done()

        snapshot = aggregator.today_snapshot(start + timedelta(hours=2))
        assert snapshot.temp_min == 10.0
        assert snapshot.temp_max == 20.0
        # 10 in effect for 1h, 20 in effect for 1h => mean 15
        assert snapshot.temp_mean == pytest.approx(15.0)
    finally:
        await aggregator.async_shutdown()


async def test_unknown_state_is_ignored_by_live_listener(
    hass: HomeAssistant, freezer: Any
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    start = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)
    freezer.move_to(start)

    aggregator = WeatherAggregator(hass, entry)
    await aggregator.async_setup()
    try:
        hass.states.async_set(MOCK_TEMPERATURE_ENTITY, "unknown")
        await hass.async_block_till_done()
        assert aggregator.today_snapshot(start).temp_min is None

        hass.states.async_set(
            MOCK_TEMPERATURE_ENTITY, "15.0", {"unit_of_measurement": "°C"}
        )
        await hass.async_block_till_done()
        assert aggregator.today_snapshot(start).temp_min == 15.0
    finally:
        await aggregator.async_shutdown()


async def test_live_rain_updates_feed_rain_accumulator(
    hass: HomeAssistant, freezer: Any
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    start = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)
    freezer.move_to(start)

    aggregator = WeatherAggregator(hass, entry)
    await aggregator.async_setup()
    try:
        hass.states.async_set(
            MOCK_DAILY_RAINFALL_ENTITY, "1.0", {"unit_of_measurement": "mm"}
        )
        await hass.async_block_till_done()

        freezer.move_to(start + timedelta(minutes=10))
        hass.states.async_set(
            MOCK_DAILY_RAINFALL_ENTITY, "2.5", {"unit_of_measurement": "mm"}
        )
        await hass.async_block_till_done()

        assert aggregator.today_snapshot(start).rain_mm == pytest.approx(1.5)
    finally:
        await aggregator.async_shutdown()


async def test_setup_registers_and_shutdown_unsubs_listeners(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    aggregator = WeatherAggregator(hass, entry)
    await aggregator.async_setup()
    assert aggregator._unsub_state is not None
    assert aggregator._unsub_midnight is not None

    await aggregator.async_shutdown()
    assert aggregator._unsub_state is None
    assert aggregator._unsub_midnight is None


async def test_handle_midnight_finalizes_history_and_resets(
    hass: HomeAssistant, freezer: Any
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    start = datetime(2026, 7, 13, 10, 0, tzinfo=UTC)
    freezer.move_to(start)

    aggregator = WeatherAggregator(hass, entry)
    await aggregator.async_setup()
    try:
        hass.states.async_set(
            MOCK_TEMPERATURE_ENTITY, "18.0", {"unit_of_measurement": "°C"}
        )
        # First-ever rain sample only seeds the baseline (delta=0 by design);
        # a second sample is needed to produce a real, non-zero delta.
        hass.states.async_set(
            MOCK_DAILY_RAINFALL_ENTITY, "3.0", {"unit_of_measurement": "mm"}
        )
        await hass.async_block_till_done()
        freezer.move_to(start + timedelta(hours=1))
        hass.states.async_set(
            MOCK_DAILY_RAINFALL_ENTITY, "4.5", {"unit_of_measurement": "mm"}
        )
        await hass.async_block_till_done()

        midnight = datetime(2026, 7, 14, 0, 0, tzinfo=UTC)
        await aggregator._handle_midnight(midnight)

        finalized = aggregator.get_finalized_day(date(2026, 7, 13))
        assert finalized is not None
        assert finalized.temp_min == 18.0
        assert finalized.rain_mm == pytest.approx(1.5)

        # New day: rain resets to 0; temperature carries the last value forward.
        today = aggregator.today_snapshot(midnight)
        assert today.day == date(2026, 7, 14)
        assert today.rain_mm == pytest.approx(0.0)
        assert today.temp_min == 18.0
    finally:
        await aggregator.async_shutdown()


async def test_persistence_round_trip_survives_restart(
    hass: HomeAssistant, freezer: Any
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)

    start = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)
    freezer.move_to(start)

    aggregator1 = WeatherAggregator(hass, entry)
    await aggregator1.async_setup()
    hass.states.async_set(
        MOCK_TEMPERATURE_ENTITY, "12.0", {"unit_of_measurement": "°C"}
    )
    hass.states.async_set(
        MOCK_DAILY_RAINFALL_ENTITY, "1.5", {"unit_of_measurement": "mm"}
    )
    await hass.async_block_till_done()

    freezer.move_to(start + timedelta(minutes=30))
    hass.states.async_set(
        MOCK_DAILY_RAINFALL_ENTITY, "2.0", {"unit_of_measurement": "mm"}
    )
    await hass.async_block_till_done()

    # Forces an immediate (non-debounced) flush.
    await aggregator1.async_shutdown()

    # Simulate a restart: a brand new aggregator instance against the same Store.
    aggregator2 = WeatherAggregator(hass, entry)
    await aggregator2.async_setup()
    try:
        snapshot = aggregator2.today_snapshot(start + timedelta(minutes=30))
        assert snapshot.temp_min == 12.0
        assert snapshot.rain_mm == pytest.approx(0.5)
    finally:
        await aggregator2.async_shutdown()


async def test_backfill_replays_history_when_no_persisted_state(
    hass: HomeAssistant,
) -> None:
    """When there's no persisted state for today, a bounded recorder backfill
    reconstructs today's accumulators by replaying history chronologically
    through the same reset-aware logic used for live updates."""
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    hass.config.components.add("recorder")

    start_of_day = dt_util.start_of_local_day()
    history_data = {
        MOCK_TEMPERATURE_ENTITY: [
            State(
                MOCK_TEMPERATURE_ENTITY,
                "10.0",
                {"unit_of_measurement": "°C"},
                last_updated=start_of_day + timedelta(hours=1),
            ),
            State(
                MOCK_TEMPERATURE_ENTITY,
                "14.0",
                {"unit_of_measurement": "°C"},
                last_updated=start_of_day + timedelta(hours=3),
            ),
        ],
        MOCK_DAILY_RAINFALL_ENTITY: [
            State(
                MOCK_DAILY_RAINFALL_ENTITY,
                "0.0",
                {"unit_of_measurement": "mm"},
                last_updated=start_of_day + timedelta(hours=1),
            ),
            State(
                MOCK_DAILY_RAINFALL_ENTITY,
                "1.2",
                {"unit_of_measurement": "mm"},
                last_updated=start_of_day + timedelta(hours=2),
            ),
        ],
    }

    class _FakeRecorder:
        async def async_add_executor_job(self, func: Any, *args: Any) -> Any:
            return func(*args)

    aggregator = WeatherAggregator(hass, entry)
    with (
        patch(
            "custom_components.garden_irrigation.weather.get_instance",
            return_value=_FakeRecorder(),
        ),
        patch(
            "custom_components.garden_irrigation.weather.history.get_significant_states",
            return_value=history_data,
        ),
    ):
        await aggregator.async_setup()
    try:
        snapshot = aggregator.today_snapshot(start_of_day + timedelta(hours=4))
        assert snapshot.temp_min == 10.0
        assert snapshot.temp_max == 14.0
        # First backfilled rain sample seeds the baseline (delta=0); only the
        # second contributes the 1.2mm delta - identical to the live rule.
        assert snapshot.rain_mm == pytest.approx(1.2)
    finally:
        await aggregator.async_shutdown()


async def test_backfill_skipped_when_recorder_unavailable(hass: HomeAssistant) -> None:
    """No recorder loaded: setup must not raise, and simply starts empty."""
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    assert "recorder" not in hass.config.components

    aggregator = WeatherAggregator(hass, entry)
    await aggregator.async_setup()
    try:
        snapshot = aggregator.today_snapshot()
        assert snapshot.temp_min is None
    finally:
        await aggregator.async_shutdown()


async def test_backfill_not_used_when_today_already_persisted(
    hass: HomeAssistant, freezer: Any
) -> None:
    """If today's state was already restored from Store, backfill must be
    skipped entirely (it is only a fallback for missing/stale state)."""
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    hass.config.components.add("recorder")

    start = datetime(2026, 7, 13, 6, 0, tzinfo=UTC)
    freezer.move_to(start)

    aggregator1 = WeatherAggregator(hass, entry)
    await aggregator1.async_setup()
    hass.states.async_set(MOCK_TEMPERATURE_ENTITY, "9.0", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    await aggregator1.async_shutdown()

    aggregator2 = WeatherAggregator(hass, entry)
    with patch(
        "custom_components.garden_irrigation.weather.get_instance",
        side_effect=AssertionError("backfill must not run when today's state exists"),
    ):
        await aggregator2.async_setup()
    try:
        assert aggregator2.today_snapshot(start).temp_min == 9.0
    finally:
        await aggregator2.async_shutdown()
