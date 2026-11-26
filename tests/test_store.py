"""Tests for the persistence store."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.garden_irrigation.store import (
    DayRecord,
    GardenIrrigationStore,
    IrrigationRecord,
)


def _day(day: str) -> DayRecord:
    return {
        "date": day,
        "et0_mm": 3.0,
        "etc_mm": 2.85,
        "rain_mm": 0.0,
        "effective_rain_mm": 0.0,
        "irrigation_mm": 0.0,
        "deficit_mm": 5.0,
        "et0_estimate": False,
        "incomplete": [],
    }


def _irrigation(timestamp: str) -> IrrigationRecord:
    return {
        "timestamp": timestamp,
        "source": "mains",
        "mm": 3.75,
        "minutes": 15.0,
        "note": None,
    }


async def test_empty_store_creates_default_zone(hass: HomeAssistant) -> None:
    store = GardenIrrigationStore(hass, "entry")
    await store.async_load()

    zone = store.zone("z1")
    assert zone == {
        "deficit_mm": None,
        "last_balance_date": None,
        "days": [],
        "irrigations": [],
    }
    assert store.zone_ids() == ["z1"]


async def test_roundtrip(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    store = GardenIrrigationStore(hass, "entry")
    await store.async_load()
    store.zone("z1")["deficit_mm"] = 7.5
    store.zone("z1")["days"].append(_day("2026-11-25"))
    await store.async_save()

    reloaded = GardenIrrigationStore(hass, "entry")
    await reloaded.async_load()
    assert reloaded.zone("z1")["deficit_mm"] == 7.5
    assert reloaded.zone("z1")["days"] == [_day("2026-11-25")]


async def test_prune_zones(hass: HomeAssistant) -> None:
    store = GardenIrrigationStore(hass, "entry")
    await store.async_load()
    store.zone("keep")
    store.zone("drop")

    assert store.prune_zones(["keep"]) is True
    assert store.zone_ids() == ["keep"]
    assert store.prune_zones(["keep"]) is False


async def test_prune_history_keeps_365_days(hass: HomeAssistant) -> None:
    store = GardenIrrigationStore(hass, "entry")
    await store.async_load()
    zone = store.zone("z1")
    zone["days"] = [_day("2025-11-25"), _day("2025-11-26"), _day("2026-11-25")]
    zone["irrigations"] = [
        _irrigation("2025-11-25T07:00:00+01:00"),
        _irrigation("2026-11-20T07:00:00+01:00"),
    ]

    assert store.prune_history(date(2026, 11, 26)) is True
    assert [d["date"] for d in zone["days"]] == ["2025-11-26", "2026-11-25"]
    assert [r["timestamp"] for r in zone["irrigations"]] == [
        "2026-11-20T07:00:00+01:00"
    ]
    assert store.prune_history(date(2026, 11, 26)) is False
