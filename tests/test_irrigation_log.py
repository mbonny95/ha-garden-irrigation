"""Tests for the garden_irrigation manual irrigation-cycle log (Milestone 6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.garden_irrigation.const import (
    DOMAIN,
    SOURCE_MAINS_WATER,
    SOURCE_RAINWATER_TANK,
    ZONE_1,
    ZONE_2,
)
from custom_components.garden_irrigation.coordinator import GardenIrrigationCoordinator
from custom_components.garden_irrigation.irrigation_log import (
    EVENT_RETENTION_DAYS,
    SERVICE_RECORD_IRRIGATION,
)

from .const import (
    rain_step_input,
    soil_step_input,
    telegram_step_input,
    user_step_input,
    zones_step_input,
)

# zones_step_input() default: zone1 mains=0.25mm/min area=38m2, zone2
# mains=0.175mm/min area=72m2, neither zone's tank calibrated (unset).
ZONE1_MAINS_MM_PER_MIN = 0.25
ZONE1_AREA_M2 = 38.0
ZONE1_TANK_MM_PER_MIN = 0.1


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


# ---------------------------------------------------------------------------
# Calibration: mains is always calibrated by default test config; tank isn't
# ---------------------------------------------------------------------------


async def test_calibrated_source_updates_balance_ledger(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    log = coordinator.irrigation_log

    event = await log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_MAINS_WATER, duration_minutes=10.0
    )

    assert event.calibrated is True
    assert event.mm == pytest.approx(10.0 * ZONE1_MAINS_MM_PER_MIN)
    assert event.liters == pytest.approx(event.mm * ZONE1_AREA_M2)

    as_of = event.timestamp + timedelta(seconds=1)
    assert coordinator.balance.weekly_irrigation_mm(ZONE_1, as_of) == pytest.approx(
        event.mm
    )


async def test_uncalibrated_source_persists_event_without_updating_deficit(
    hass: HomeAssistant,
) -> None:
    """Rainwater tank has no configured mm/minute by default: the event is
    still saved, but mm/liters are None and the balance ledger is untouched."""
    coordinator = _coordinator(hass)
    log = coordinator.irrigation_log

    event = await log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_RAINWATER_TANK, duration_minutes=10.0
    )

    assert event.calibrated is False
    assert event.mm is None
    assert event.liters is None
    assert len(log.events_for_zone(ZONE_1)) == 1

    as_of = event.timestamp + timedelta(seconds=1)
    assert coordinator.balance.weekly_irrigation_mm(ZONE_1, as_of) == 0.0


async def test_tank_becomes_calibrated_when_configured(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass, zone1_mm_per_minute_tank=ZONE1_TANK_MM_PER_MIN)
    log = coordinator.irrigation_log

    event = await log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_RAINWATER_TANK, duration_minutes=8.0
    )

    assert event.calibrated is True
    assert event.mm == pytest.approx(8.0 * ZONE1_TANK_MM_PER_MIN)
    assert event.liters == pytest.approx(event.mm * ZONE1_AREA_M2)


# ---------------------------------------------------------------------------
# Idempotency / double-submission protection
# ---------------------------------------------------------------------------


async def test_duplicate_idempotency_key_is_a_noop(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    log = coordinator.irrigation_log

    first = await log.async_record_irrigation(
        zone_id=ZONE_1,
        source=SOURCE_MAINS_WATER,
        duration_minutes=10.0,
        idempotency_key="retry-1",
    )
    second = await log.async_record_irrigation(
        zone_id=ZONE_1,
        source=SOURCE_MAINS_WATER,
        duration_minutes=10.0,
        idempotency_key="retry-1",
    )

    assert second == first
    assert len(log.events_for_zone(ZONE_1)) == 1

    as_of = first.timestamp + timedelta(seconds=1)
    # The balance ledger must reflect exactly ONE contribution, not two.
    assert coordinator.balance.weekly_irrigation_mm(ZONE_1, as_of) == pytest.approx(
        first.mm
    )


async def test_different_idempotency_keys_both_record(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    log = coordinator.irrigation_log

    await log.async_record_irrigation(
        zone_id=ZONE_1,
        source=SOURCE_MAINS_WATER,
        duration_minutes=10.0,
        idempotency_key="a",
    )
    await log.async_record_irrigation(
        zone_id=ZONE_1,
        source=SOURCE_MAINS_WATER,
        duration_minutes=10.0,
        idempotency_key="b",
    )

    assert len(log.events_for_zone(ZONE_1)) == 2


# ---------------------------------------------------------------------------
# Aggregates: derived on demand from the event list, per source
# ---------------------------------------------------------------------------


async def test_aggregates_by_source(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass, zone1_mm_per_minute_tank=ZONE1_TANK_MM_PER_MIN)
    log = coordinator.irrigation_log

    await log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_MAINS_WATER, duration_minutes=10.0
    )
    await log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_MAINS_WATER, duration_minutes=5.0
    )
    await log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_RAINWATER_TANK, duration_minutes=4.0
    )

    totals = log.totals_by_source(ZONE_1)

    mains_mm = 15.0 * ZONE1_MAINS_MM_PER_MIN
    assert totals[SOURCE_MAINS_WATER].count == 2
    assert totals[SOURCE_MAINS_WATER].mm == pytest.approx(mains_mm)
    assert totals[SOURCE_MAINS_WATER].liters == pytest.approx(mains_mm * ZONE1_AREA_M2)

    tank_mm = 4.0 * ZONE1_TANK_MM_PER_MIN
    assert totals[SOURCE_RAINWATER_TANK].count == 1
    assert totals[SOURCE_RAINWATER_TANK].mm == pytest.approx(tank_mm)

    # A second zone's events must never leak into zone 1's aggregates.
    await log.async_record_irrigation(
        zone_id=ZONE_2, source=SOURCE_MAINS_WATER, duration_minutes=10.0
    )
    assert log.totals_by_source(ZONE_1)[SOURCE_MAINS_WATER].count == 2


async def test_aggregate_uncalibrated_event_counts_but_no_mm(
    hass: HomeAssistant,
) -> None:
    """An uncalibrated event still counts toward `count`, but contributes
    nothing to the mm/liters sums (there is nothing real to sum)."""
    coordinator = _coordinator(hass)
    log = coordinator.irrigation_log

    await log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_RAINWATER_TANK, duration_minutes=10.0
    )

    aggregate = log.aggregate(ZONE_1, source=SOURCE_RAINWATER_TANK)
    assert aggregate.count == 1
    assert aggregate.mm == 0.0
    assert aggregate.liters == 0.0


# ---------------------------------------------------------------------------
# Timestamp: always "now", never client-supplied/backdated
# ---------------------------------------------------------------------------


async def test_timestamp_is_always_current(hass: HomeAssistant, freezer: Any) -> None:
    frozen_now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    freezer.move_to(frozen_now)
    coordinator = _coordinator(hass)
    log = coordinator.irrigation_log

    event = await log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_MAINS_WATER, duration_minutes=5.0
    )

    assert event.timestamp == frozen_now


async def test_service_schema_rejects_unknown_timestamp_field(
    hass: HomeAssistant,
) -> None:
    """The schema has no timestamp/backdating field at all - an attempt to
    pass one is rejected structurally, not merely ignored."""
    coordinator = _coordinator(hass)
    await coordinator.async_setup()
    try:
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RECORD_IRRIGATION,
                {
                    "zone": ZONE_1,
                    "source": SOURCE_MAINS_WATER,
                    "duration_minutes": 5.0,
                    "timestamp": "2020-01-01T00:00:00+00:00",
                },
                blocking=True,
            )
    finally:
        await coordinator.async_shutdown()


# ---------------------------------------------------------------------------
# Duration validation (service schema layer)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("duration_minutes", [0, -1, 15.1, 20])
async def test_service_rejects_invalid_duration(
    hass: HomeAssistant, duration_minutes: float
) -> None:
    coordinator = _coordinator(hass)
    await coordinator.async_setup()
    try:
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RECORD_IRRIGATION,
                {
                    "zone": ZONE_1,
                    "source": SOURCE_MAINS_WATER,
                    "duration_minutes": duration_minutes,
                },
                blocking=True,
            )
    finally:
        await coordinator.async_shutdown()


async def test_service_accepts_boundary_duration(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    await coordinator.async_setup()
    try:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RECORD_IRRIGATION,
            {"zone": ZONE_1, "source": SOURCE_MAINS_WATER, "duration_minutes": 15.0},
            blocking=True,
        )
        assert len(coordinator.irrigation_log.events_for_zone(ZONE_1)) == 1
    finally:
        await coordinator.async_shutdown()


async def test_service_rejects_unknown_zone_and_source(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)
    await coordinator.async_setup()
    try:
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RECORD_IRRIGATION,
                {
                    "zone": "not_a_zone",
                    "source": SOURCE_MAINS_WATER,
                    "duration_minutes": 5.0,
                },
                blocking=True,
            )
    finally:
        await coordinator.async_shutdown()


# ---------------------------------------------------------------------------
# Retention: events older than 365 days are pruned
# ---------------------------------------------------------------------------


async def test_retention_prunes_events_older_than_365_days(
    hass: HomeAssistant, freezer: Any
) -> None:
    start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(start)
    coordinator = _coordinator(hass)
    log = coordinator.irrigation_log

    old_event = await log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_MAINS_WATER, duration_minutes=5.0
    )
    assert len(log.events_for_zone(ZONE_1)) == 1

    freezer.move_to(start + timedelta(days=EVENT_RETENTION_DAYS + 1))
    new_event = await log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_MAINS_WATER, duration_minutes=5.0
    )

    remaining = log.events_for_zone(ZONE_1)
    assert old_event.id not in [event.id for event in remaining]
    assert new_event.id in [event.id for event in remaining]


async def test_retention_keeps_events_within_365_days(
    hass: HomeAssistant, freezer: Any
) -> None:
    start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    freezer.move_to(start)
    coordinator = _coordinator(hass)
    log = coordinator.irrigation_log

    await log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_MAINS_WATER, duration_minutes=5.0
    )

    freezer.move_to(start + timedelta(days=EVENT_RETENTION_DAYS - 1))
    await log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_MAINS_WATER, duration_minutes=5.0
    )

    assert len(log.events_for_zone(ZONE_1)) == 2


# ---------------------------------------------------------------------------
# Persistence round-trip
# ---------------------------------------------------------------------------


async def test_events_survive_setup_shutdown_roundtrip(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=_full_entry_data())
    entry.add_to_hass(hass)
    coordinator1 = GardenIrrigationCoordinator(hass, entry)
    await coordinator1.async_setup()
    await coordinator1.irrigation_log.async_record_irrigation(
        zone_id=ZONE_1, source=SOURCE_MAINS_WATER, duration_minutes=10.0
    )
    await coordinator1.async_shutdown()

    coordinator2 = GardenIrrigationCoordinator(hass, entry)
    await coordinator2.async_setup()
    try:
        restored = coordinator2.irrigation_log.events_for_zone(ZONE_1)
        assert len(restored) == 1
        assert restored[0].mm == pytest.approx(10.0 * ZONE1_MAINS_MM_PER_MIN)
    finally:
        await coordinator2.async_shutdown()


# ---------------------------------------------------------------------------
# Minimal coordinator integration: service registration + coordinator.data
# ---------------------------------------------------------------------------


async def test_coordinator_registers_and_removes_service(hass: HomeAssistant) -> None:
    coordinator = _coordinator(hass)

    await coordinator.async_setup()
    assert hass.services.has_service(DOMAIN, SERVICE_RECORD_IRRIGATION)

    await coordinator.async_shutdown()
    assert not hass.services.has_service(DOMAIN, SERVICE_RECORD_IRRIGATION)


async def test_full_service_call_updates_coordinator_data(
    hass: HomeAssistant,
) -> None:
    coordinator = _coordinator(hass)
    await coordinator.async_setup()
    try:
        await coordinator.async_refresh()

        await hass.services.async_call(
            DOMAIN,
            SERVICE_RECORD_IRRIGATION,
            {"zone": ZONE_1, "source": SOURCE_MAINS_WATER, "duration_minutes": 10.0},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert coordinator.data is not None
        irrigation = coordinator.data["irrigation"][ZONE_1]
        assert irrigation[SOURCE_MAINS_WATER].count == 1
        assert irrigation[SOURCE_MAINS_WATER].mm == pytest.approx(
            10.0 * ZONE1_MAINS_MM_PER_MIN
        )
    finally:
        await coordinator.async_shutdown()
