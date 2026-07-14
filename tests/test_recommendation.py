"""Tests for the garden_irrigation recommendation engine (Milestone 7)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.balance import (
    SKIPPED_ALREADY_PROCESSED,
    SKIPPED_ET0_UNAVAILABLE,
    ZoneBalanceResult,
)
from custom_components.garden_irrigation.const import (
    DEFAULT_AWC_MM_PER_M,
    DEFAULT_BLOCK_PAUSE_MINUTES,
    DEFAULT_CALIBRATION_DAYS,
    DEFAULT_KC,
    DEFAULT_MAX_CYCLE_MINUTES,
    DEFAULT_MIN_INTERVAL_HOURS,
    DEFAULT_P_DEPLETION_FRACTION,
    DEFAULT_RAIN_EFFECTIVE_FACTOR,
    DEFAULT_ROOT_DEPTH_MM,
    DEFAULT_WEEKLY_CAP_MM,
    DOMAIN,
    SOURCE_MAINS_WATER,
    SOURCE_RAINWATER_TANK,
    ZONE_1,
)
from custom_components.garden_irrigation.coordinator import GardenIrrigationCoordinator
from custom_components.garden_irrigation.recommendation import (
    LIMIT_MIN_INTERVAL_NOT_ELAPSED,
    LIMIT_WEEKLY_CAP_PARTIAL,
    LIMIT_WEEKLY_CAP_REACHED,
    REASON_NOT_READY_PENDING,
    REASON_NOT_READY_PREVIEW_ET0_UNAVAILABLE,
    REASON_WH51_CONTRADICTS,
    REASON_WH51_CORROBORATES,
    WH51_STATUS_DIAGNOSTIC,
    WH51_STATUS_DRY,
    WH51_STATUS_WET,
)

from .const import (
    MOCK_ZONE1_SOIL_ENTITY,
    rain_step_input,
    soil_step_input,
    telegram_step_input,
    user_step_input,
    zones_step_input,
)

TAW_MM = (DEFAULT_ROOT_DEPTH_MM / 1000.0) * DEFAULT_AWC_MM_PER_M
RAW_MM = TAW_MM * DEFAULT_P_DEPLETION_FRACTION
ZONE1_MAINS_MM_PER_MIN = 0.25


def _full_entry_data(**zone_overrides: Any) -> dict[str, Any]:
    return {
        **user_step_input(),
        **rain_step_input(),
        **soil_step_input(),
        **zones_step_input(**zone_overrides),
        **telegram_step_input(),
    }


def _coordinator(
    hass: HomeAssistant, **zone_overrides: Any
) -> GardenIrrigationCoordinator:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data(**zone_overrides))
    entry.add_to_hass(hass)
    return GardenIrrigationCoordinator(hass, entry)


def _balance_result(
    *,
    zone_id: str = ZONE_1,
    day: date = date(2026, 6, 1),
    applied: bool = True,
    skipped_reason: str | None = None,
    deficit_mm: float = 20.0,
    taw_mm: float = TAW_MM,
    raw_mm: float = RAW_MM,
    irrigation_7d_mm: float = 0.0,
    weekly_cap_mm: float = DEFAULT_WEEKLY_CAP_MM,
    weekly_cap_reached: bool = False,
) -> ZoneBalanceResult:
    return ZoneBalanceResult(
        zone_id=zone_id,
        day=day,
        applied=applied,
        skipped_reason=skipped_reason,
        etc_mm=5.0 if applied else None,
        eff_rain_mm=0.0 if applied else None,
        irrigation_mm=0.0,
        deficit_mm=deficit_mm,
        taw_mm=taw_mm,
        raw_mm=raw_mm,
        irrigation_7d_mm=irrigation_7d_mm,
        weekly_cap_mm=weekly_cap_mm,
        weekly_cap_reached=weekly_cap_reached,
    )


# ---------------------------------------------------------------------------
# Core decision: dry / wet scenarios
# ---------------------------------------------------------------------------


async def test_dry_scenario_recommends_full_deficit_when_no_limits(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    result = _balance_result(deficit_mm=20.0)  # 20 >= RAW_MM (15)

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    final = bundle.final
    assert final.ready is True
    assert final.needs_irrigation is True
    assert final.recommended_mm == pytest.approx(20.0)
    assert final.limits_applied == ()
    assert final.estimated_liters == pytest.approx(20.0 * 38.0)  # zone1 area default

    mains = final.sources[SOURCE_MAINS_WATER]
    assert mains.calibrated is True
    assert mains.minutes == pytest.approx(20.0 / ZONE1_MAINS_MM_PER_MIN)


async def test_wet_scenario_recommends_nothing(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    result = _balance_result(deficit_mm=5.0)  # 5 < RAW_MM (15)

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    final = bundle.final
    assert final.needs_irrigation is False
    assert final.recommended_mm == 0.0
    assert final.limits_applied == ()


# ---------------------------------------------------------------------------
# Limits: weekly cap (full/partial), 48h minimum interval
# ---------------------------------------------------------------------------


async def test_weekly_cap_fully_reached_blocks_recommendation(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    result = _balance_result(
        deficit_mm=20.0,
        irrigation_7d_mm=DEFAULT_WEEKLY_CAP_MM,
        weekly_cap_reached=True,
    )

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    final = bundle.final
    assert final.needs_irrigation is False
    assert final.recommended_mm == 0.0
    assert LIMIT_WEEKLY_CAP_REACHED in final.limits_applied
    # (C) Fully reached is never also reported as "partial".
    assert LIMIT_WEEKLY_CAP_PARTIAL not in final.limits_applied


async def test_weekly_cap_partial_limits_recommended_amount(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    remaining_cap = 6.0
    result = _balance_result(
        deficit_mm=20.0,
        irrigation_7d_mm=DEFAULT_WEEKLY_CAP_MM - remaining_cap,
        weekly_cap_reached=False,
    )

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    final = bundle.final
    assert final.needs_irrigation is True  # cap not fully consumed, still surmountable
    assert final.recommended_mm == pytest.approx(remaining_cap)
    assert LIMIT_WEEKLY_CAP_PARTIAL in final.limits_applied
    assert LIMIT_WEEKLY_CAP_REACHED not in final.limits_applied


async def test_weekly_cap_partial_explicit_cap_remaining_less_than_deficit(
    hass: HomeAssistant,
) -> None:
    """(A) `0 < cap_remaining_mm < deficit_mm`: the recommendation is capped
    to what's left, flagged explicitly as partial, and irrigation is still
    recommended (the cap isn't fully consumed)."""
    coordinator = _coordinator(hass)
    deficit_mm = 25.0
    cap_remaining_mm = 4.0
    result = _balance_result(
        deficit_mm=deficit_mm,
        irrigation_7d_mm=DEFAULT_WEEKLY_CAP_MM - cap_remaining_mm,
        weekly_cap_reached=False,
    )

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    final = bundle.final
    assert final.needs_irrigation is True
    assert final.recommended_mm == pytest.approx(cap_remaining_mm)
    assert LIMIT_WEEKLY_CAP_PARTIAL in final.limits_applied
    assert LIMIT_WEEKLY_CAP_REACHED not in final.limits_applied


async def test_weekly_cap_remaining_exactly_equal_to_deficit_is_not_partial(
    hass: HomeAssistant,
) -> None:
    """(B) Exact boundary: `cap_remaining_mm == deficit_mm` covers the whole
    deficit in one shot - not a "partial" cap, even though the cap is fully
    consumed by this recommendation."""
    coordinator = _coordinator(hass)
    deficit_mm = 20.0  # >= RAW_MM (15) -> raw_exceeded is True
    result = _balance_result(
        deficit_mm=deficit_mm,
        irrigation_7d_mm=DEFAULT_WEEKLY_CAP_MM - deficit_mm,
        weekly_cap_reached=False,
    )

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    final = bundle.final
    assert final.needs_irrigation is True
    assert final.recommended_mm == pytest.approx(deficit_mm)
    assert LIMIT_WEEKLY_CAP_PARTIAL not in final.limits_applied
    assert LIMIT_WEEKLY_CAP_REACHED not in final.limits_applied


async def test_min_interval_not_elapsed_never_reports_partial_cap(
    hass: HomeAssistant, freezer: Any
) -> None:
    """(D) A cap that WOULD be partial is irrelevant once the 48h minimum
    interval blocks the recommendation outright - only
    LIMIT_MIN_INTERVAL_NOT_ELAPSED should appear, never LIMIT_WEEKLY_CAP_PARTIAL,
    and recommended_mm stays 0.0."""
    freezer.move_to(datetime(2026, 6, 1, 8, 0, tzinfo=UTC))
    coordinator = _coordinator(hass)
    await coordinator.irrigation_log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_MAINS_WATER, duration_minutes=10.0
    )

    freezer.move_to(datetime(2026, 6, 1, 8, 0, tzinfo=UTC) + timedelta(hours=10))
    # cap_remaining_mm (4.0) < deficit_mm (25.0) - would be "partial" on its
    # own, but the min-interval block takes precedence.
    result = _balance_result(
        deficit_mm=25.0,
        irrigation_7d_mm=DEFAULT_WEEKLY_CAP_MM - 4.0,
        weekly_cap_reached=False,
    )
    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    final = bundle.final
    assert LIMIT_MIN_INTERVAL_NOT_ELAPSED in final.limits_applied
    assert LIMIT_WEEKLY_CAP_PARTIAL not in final.limits_applied
    assert final.recommended_mm == 0.0


async def test_recommended_mm_zero_with_calibrated_mains_reports_zero_minutes(
    hass: HomeAssistant,
) -> None:
    """(F) When recommended_mm is 0.0 (e.g. deficit below RAW) but the source
    IS calibrated, minutes is 0.0 and blocks is empty - not None/invented,
    fixing today's semantics against an accidental future regression."""
    coordinator = _coordinator(hass)  # zone1 mains is calibrated by default
    result = _balance_result(deficit_mm=5.0)  # 5 < RAW_MM (15) -> no irrigation

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    final = bundle.final
    assert final.recommended_mm == 0.0
    mains = final.sources[SOURCE_MAINS_WATER]
    assert mains.calibrated is True
    assert mains.minutes == 0.0
    assert mains.blocks == ()


async def test_min_interval_not_elapsed_blocks_recommendation(
    hass: HomeAssistant, freezer: Any
) -> None:
    freezer.move_to(datetime(2026, 6, 1, 8, 0, tzinfo=UTC))
    coordinator = _coordinator(hass)
    await coordinator.irrigation_log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_MAINS_WATER, duration_minutes=10.0
    )

    freezer.move_to(datetime(2026, 6, 1, 8, 0, tzinfo=UTC) + timedelta(hours=10))
    result = _balance_result(deficit_mm=20.0)
    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    final = bundle.final
    assert final.needs_irrigation is False
    assert final.recommended_mm == 0.0
    assert LIMIT_MIN_INTERVAL_NOT_ELAPSED in final.limits_applied


async def test_min_interval_elapsed_allows_recommendation(
    hass: HomeAssistant, freezer: Any
) -> None:
    start = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(start)
    coordinator = _coordinator(hass)
    await coordinator.irrigation_log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_MAINS_WATER, duration_minutes=10.0
    )

    freezer.move_to(start + timedelta(hours=DEFAULT_MIN_INTERVAL_HOURS + 1))
    result = _balance_result(deficit_mm=20.0)
    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    final = bundle.final
    assert final.needs_irrigation is True
    assert LIMIT_MIN_INTERVAL_NOT_ELAPSED not in final.limits_applied


# ---------------------------------------------------------------------------
# Not ready / unknown pattern: no invented numbers
# ---------------------------------------------------------------------------


async def test_final_not_ready_when_et0_was_unavailable(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    result = _balance_result(applied=False, skipped_reason=SKIPPED_ET0_UNAVAILABLE)

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    final = bundle.final
    assert final.ready is False
    assert final.needs_irrigation is None
    assert final.recommended_mm is None
    assert final.sources == {}
    # deficit/taw/raw are still informational, never hidden.
    assert final.deficit_mm == result.deficit_mm


async def test_final_not_ready_when_pending(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    result = _balance_result(applied=False, skipped_reason=None)

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    final = bundle.final
    assert final.ready is False
    assert final.reasons == (REASON_NOT_READY_PENDING,)


async def test_final_ready_when_already_processed(hass: HomeAssistant) -> None:
    """A repeat (idempotent-skip) balance result is still a READY final."""
    coordinator = _coordinator(hass)
    result = _balance_result(
        applied=False, skipped_reason=SKIPPED_ALREADY_PROCESSED, deficit_mm=20.0
    )

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    assert bundle.final.ready is True
    assert bundle.final.needs_irrigation is True


async def test_preview_not_ready_when_today_et0_unavailable(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    result = _balance_result(deficit_mm=20.0)

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=None, today_rain_mm=0.0
    )

    preview = bundle.preview
    assert preview.ready is False
    assert preview.reasons == (REASON_NOT_READY_PREVIEW_ET0_UNAVAILABLE,)
    assert preview.needs_irrigation is None
    # Still reports the currently-known (persisted) deficit informationally.
    assert preview.deficit_mm == coordinator.balance.current_deficit_mm(ZONE_1)


# ---------------------------------------------------------------------------
# Block plan: <=15 min per block, pause between (never after) blocks
# ---------------------------------------------------------------------------


async def test_block_plan_single_block_under_15_minutes(hass: HomeAssistant) -> None:
    # A higher mm/minute rate than the zone default so that a deficit which
    # still exceeds RAW (15mm) needs fewer than 15 minutes to deliver.
    coordinator = _coordinator(hass, zone1_mm_per_minute_mains=2.0)
    deficit_mm = 20.0  # >= RAW_MM (15) -> irrigation is needed
    result = _balance_result(deficit_mm=deficit_mm)

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    blocks = bundle.final.sources[SOURCE_MAINS_WATER].blocks
    assert len(blocks) == 1
    assert blocks[0].minutes == pytest.approx(10.0)
    assert blocks[0].pause_after_minutes == 0.0


async def test_block_plan_splits_into_multiple_blocks_with_pause(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass, zone1_mm_per_minute_mains=1.0)
    total_minutes = 32.0  # -> 15 + 15 + 2 minutes, two pauses
    deficit_mm = total_minutes * 1.0  # >= RAW_MM (15) -> irrigation is needed
    # A generous weekly_cap_mm so the 30mm default doesn't clip this deficit
    # (that clipping behavior is covered separately by the weekly-cap tests).
    result = _balance_result(deficit_mm=deficit_mm, weekly_cap_mm=100.0)

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    blocks = bundle.final.sources[SOURCE_MAINS_WATER].blocks
    assert [b.minutes for b in blocks] == pytest.approx(
        [DEFAULT_MAX_CYCLE_MINUTES, DEFAULT_MAX_CYCLE_MINUTES, 2.0]
    )
    assert blocks[0].pause_after_minutes == DEFAULT_BLOCK_PAUSE_MINUTES
    assert blocks[1].pause_after_minutes == DEFAULT_BLOCK_PAUSE_MINUTES
    assert blocks[2].pause_after_minutes == 0.0  # no pause after the last block
    assert sum(b.minutes for b in blocks) == pytest.approx(total_minutes)


async def test_uncalibrated_tank_source_reports_no_minutes(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)  # tank mm/minute left unset by default
    result = _balance_result(deficit_mm=20.0)

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    tank = bundle.final.sources[SOURCE_RAINWATER_TANK]
    assert tank.calibrated is False
    assert tank.minutes is None
    assert tank.blocks == ()


# ---------------------------------------------------------------------------
# WH51: diagnostic during calibration, soft signal afterward
# ---------------------------------------------------------------------------


async def test_wh51_diagnostic_before_calibration_complete(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    hass.states.async_set(MOCK_ZONE1_SOIL_ENTITY, "20", {"unit_of_measurement": "%"})
    result = _balance_result(deficit_mm=20.0)

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    assert bundle.final.wh51_status == WH51_STATUS_DIAGNOSTIC
    assert bundle.final.wh51_calibrated is False
    # Diagnostic-only: never corroborates/contradicts while uncalibrated.
    assert REASON_WH51_CORROBORATES not in bundle.final.reasons
    assert REASON_WH51_CONTRADICTS not in bundle.final.warnings


async def test_wh51_non_numeric_state_is_treated_as_unavailable(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    hass.states.async_set(
        MOCK_ZONE1_SOIL_ENTITY, "not_a_number", {"unit_of_measurement": "%"}
    )
    result = _balance_result(deficit_mm=20.0)

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    assert bundle.final.wh51_status == "unavailable"
    assert bundle.final.wh51_percent is None


async def test_wh51_critical_and_moderate_classification(
    hass: HomeAssistant, freezer: Any
) -> None:
    start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(start)
    coordinator = _coordinator(hass)

    hass.states.async_set(MOCK_ZONE1_SOIL_ENTITY, "60", {"unit_of_measurement": "%"})
    coordinator.recommendation.build(
        ZONE_1, _balance_result(deficit_mm=5.0), today_et0_mm=5.0, today_rain_mm=0.0
    )
    hass.states.async_set(MOCK_ZONE1_SOIL_ENTITY, "10", {"unit_of_measurement": "%"})
    coordinator.recommendation.build(
        ZONE_1, _balance_result(deficit_mm=5.0), today_et0_mm=5.0, today_rain_mm=0.0
    )

    freezer.move_to(start + timedelta(days=DEFAULT_CALIBRATION_DAYS, hours=1))
    # position = (11-10)/(60-10) = 0.02 -> at/below the "critical" threshold.
    hass.states.async_set(MOCK_ZONE1_SOIL_ENTITY, "11", {"unit_of_measurement": "%"})
    critical_bundle = coordinator.recommendation.build(
        ZONE_1, _balance_result(deficit_mm=20.0), today_et0_mm=5.0, today_rain_mm=0.0
    )
    assert critical_bundle.final.wh51_status == "critical"

    # position = (35-10)/(60-10) = 0.5 -> strictly between the dry and wet
    # thresholds: neither dry/critical nor wet.
    hass.states.async_set(MOCK_ZONE1_SOIL_ENTITY, "35", {"unit_of_measurement": "%"})
    moderate_bundle = coordinator.recommendation.build(
        ZONE_1, _balance_result(deficit_mm=20.0), today_et0_mm=5.0, today_rain_mm=0.0
    )
    assert moderate_bundle.final.wh51_status == "moderate"


async def test_wh51_soft_signal_corroborates_after_calibration(
    hass: HomeAssistant, freezer: Any
) -> None:
    start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(start)
    coordinator = _coordinator(hass)

    # Observe a wide range during the 14-day calibration window.
    hass.states.async_set(MOCK_ZONE1_SOIL_ENTITY, "60", {"unit_of_measurement": "%"})
    coordinator.recommendation.build(
        ZONE_1, _balance_result(deficit_mm=5.0), today_et0_mm=5.0, today_rain_mm=0.0
    )
    hass.states.async_set(MOCK_ZONE1_SOIL_ENTITY, "10", {"unit_of_measurement": "%"})
    coordinator.recommendation.build(
        ZONE_1, _balance_result(deficit_mm=5.0), today_et0_mm=5.0, today_rain_mm=0.0
    )

    freezer.move_to(start + timedelta(days=DEFAULT_CALIBRATION_DAYS, hours=1))
    # position = (20-10)/(60-10) = 0.2 -> above the "critical" threshold (0.1)
    # and at/below the "dry" threshold (0.3): a "dry" relative position.
    hass.states.async_set(MOCK_ZONE1_SOIL_ENTITY, "20", {"unit_of_measurement": "%"})
    result = _balance_result(deficit_mm=20.0)  # raw exceeded -> needs irrigation
    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    final = bundle.final
    assert final.wh51_calibrated is True
    assert final.wh51_status == WH51_STATUS_DRY
    assert REASON_WH51_CORROBORATES in final.reasons
    # Never a hard block: needs_irrigation is driven by deficit/limits only.
    assert final.needs_irrigation is True


async def test_wh51_soft_signal_contradicts_is_a_warning_not_a_block(
    hass: HomeAssistant, freezer: Any
) -> None:
    start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(start)
    coordinator = _coordinator(hass)

    hass.states.async_set(MOCK_ZONE1_SOIL_ENTITY, "60", {"unit_of_measurement": "%"})
    coordinator.recommendation.build(
        ZONE_1, _balance_result(deficit_mm=5.0), today_et0_mm=5.0, today_rain_mm=0.0
    )
    hass.states.async_set(MOCK_ZONE1_SOIL_ENTITY, "10", {"unit_of_measurement": "%"})
    coordinator.recommendation.build(
        ZONE_1, _balance_result(deficit_mm=5.0), today_et0_mm=5.0, today_rain_mm=0.0
    )

    freezer.move_to(start + timedelta(days=DEFAULT_CALIBRATION_DAYS, hours=1))
    # Near the observed maximum (60) -> "wet" relative position.
    hass.states.async_set(MOCK_ZONE1_SOIL_ENTITY, "58", {"unit_of_measurement": "%"})
    result = _balance_result(deficit_mm=20.0)  # raw exceeded -> needs irrigation anyway
    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=5.0, today_rain_mm=0.0
    )

    final = bundle.final
    assert final.wh51_status == WH51_STATUS_WET
    assert REASON_WH51_CONTRADICTS in final.warnings
    # Soft signal never overrides the deficit-based decision.
    assert final.needs_irrigation is True
    assert final.recommended_mm == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Preview projection: correct arithmetic, never persisted (no double count)
# ---------------------------------------------------------------------------


async def test_preview_projection_matches_manual_calculation(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    coordinator.balance._deficit[ZONE_1] = 10.0  # simulate a known starting deficit

    today_et0_mm = 4.0
    today_rain_mm = 2.0
    result = _balance_result(deficit_mm=999.0)  # final's own deficit is irrelevant here

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=today_et0_mm, today_rain_mm=today_rain_mm
    )

    prev_deficit = 10.0
    etc = today_et0_mm * DEFAULT_KC
    eff_rain = min(today_rain_mm * DEFAULT_RAIN_EFFECTIVE_FACTOR, prev_deficit + etc)
    expected_deficit = min(max(prev_deficit + etc - eff_rain, 0.0), TAW_MM)

    assert bundle.preview.ready is True
    assert bundle.preview.deficit_mm == pytest.approx(expected_deficit)


async def test_preview_subtracts_irrigation_recorded_today(
    hass: HomeAssistant, freezer: Any
) -> None:
    """(E) The preview must reflect a cycle recorded earlier TODAY (via
    irrigation_log.aggregate(since=start_of_today, until=now)), not just
    ET0/rain - this is what distinguishes it from the persisted deficit."""
    now = datetime(2026, 6, 1, 18, 0, tzinfo=UTC)
    freezer.move_to(now)
    coordinator = _coordinator(hass)
    prev_deficit = 15.0
    coordinator.balance._deficit[ZONE_1] = prev_deficit

    await coordinator.irrigation_log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_MAINS_WATER, duration_minutes=10.0
    )
    # The recording above must not itself have changed the persisted deficit
    # (only balance.py's once-a-day finalization does that).
    assert coordinator.balance.current_deficit_mm(ZONE_1) == prev_deficit

    today_et0_mm = 4.0
    today_rain_mm = 2.0
    result = _balance_result(deficit_mm=999.0)  # final's own deficit is irrelevant here

    bundle = coordinator.recommendation.build(
        ZONE_1, result, today_et0_mm=today_et0_mm, today_rain_mm=today_rain_mm
    )

    start_of_today = dt_util.start_of_local_day(now)
    irrigation_today_mm = coordinator.irrigation_log.aggregate(
        ZONE_1, since=start_of_today, until=now
    ).mm
    assert irrigation_today_mm == pytest.approx(10.0 * ZONE1_MAINS_MM_PER_MIN)

    projected_etc_mm = today_et0_mm * DEFAULT_KC
    eff_rain_mm = min(
        today_rain_mm * DEFAULT_RAIN_EFFECTIVE_FACTOR, prev_deficit + projected_etc_mm
    )
    expected_deficit = min(
        max(prev_deficit + projected_etc_mm - eff_rain_mm - irrigation_today_mm, 0.0),
        TAW_MM,
    )

    assert bundle.preview.ready is True
    assert bundle.preview.deficit_mm == pytest.approx(expected_deficit)
    # Sanity: the same-day recording actually lowers the projection relative
    # to what it would have been without it.
    no_irrigation_deficit = min(
        max(prev_deficit + projected_etc_mm - eff_rain_mm, 0.0), TAW_MM
    )
    assert bundle.preview.deficit_mm < no_irrigation_deficit


async def test_preview_never_mutates_persisted_deficit(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    coordinator.balance._deficit[ZONE_1] = 10.0
    result = _balance_result(deficit_mm=999.0)

    for _ in range(3):
        coordinator.recommendation.build(
            ZONE_1, result, today_et0_mm=4.0, today_rain_mm=0.0
        )

    # Repeated preview builds must never touch balance.py's own stored state.
    assert coordinator.balance.current_deficit_mm(ZONE_1) == 10.0


# ---------------------------------------------------------------------------
# Persistence round-trip for the WH51 calibration baseline
# ---------------------------------------------------------------------------


async def test_wh51_calibration_survives_setup_shutdown_roundtrip(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator1 = GardenIrrigationCoordinator(hass, entry)
    await coordinator1.async_setup()
    hass.states.async_set(MOCK_ZONE1_SOIL_ENTITY, "42", {"unit_of_measurement": "%"})
    coordinator1.recommendation.build(
        ZONE_1, _balance_result(deficit_mm=5.0), today_et0_mm=5.0, today_rain_mm=0.0
    )
    await coordinator1.async_shutdown()

    coordinator2 = GardenIrrigationCoordinator(hass, entry)
    await coordinator2.async_setup()
    try:
        assert coordinator2.recommendation._calibration[ZONE_1].first_seen is not None
        assert coordinator2.recommendation._calibration[ZONE_1].baseline_min == 42.0
    finally:
        await coordinator2.async_shutdown()
