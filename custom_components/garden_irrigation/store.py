"""Single versioned persistence store for the integration.

Holds, per zone (keyed by subentry id): the current soil water deficit, the
last day the balance was applied, the daily balance history and the log of
recorded irrigations. Everything is retained for RETENTION_DAYS.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import NotRequired, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, RETENTION_DAYS, STORAGE_VERSION

SAVE_DELAY_SECONDS = 10


class DayRecord(TypedDict):
    """Daily balance outcome for one zone (values in mm)."""

    date: str  # ISO date of the balanced day
    et0_mm: float | None
    etc_mm: float | None
    rain_mm: float | None
    effective_rain_mm: float | None
    irrigation_mm: float
    deficit_mm: float | None
    note: NotRequired[str]


class IrrigationRecord(TypedDict):
    """A manually recorded irrigation."""

    timestamp: str  # ISO datetime, timezone-aware
    source: str
    mm: float
    minutes: float | None
    note: str | None


class ZoneState(TypedDict):
    """Persisted state of one zone."""

    deficit_mm: float | None  # None until the user sets a starting deficit
    last_balance_date: str | None
    days: list[DayRecord]
    irrigations: list[IrrigationRecord]


class StoredData(TypedDict):
    """Top-level persisted document."""

    zones: dict[str, ZoneState]


def _empty_zone() -> ZoneState:
    return {
        "deficit_mm": None,
        "last_balance_date": None,
        "days": [],
        "irrigations": [],
    }


class GardenIrrigationStore:
    """In-memory copy of the persisted document plus save helpers."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Bind the store to one config entry."""
        self._store: Store[StoredData] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}"
        )
        self._data: StoredData = {"zones": {}}

    async def async_load(self) -> None:
        """Load the persisted document (empty document if none exists)."""
        loaded = await self._store.async_load()
        self._data = loaded if loaded is not None else {"zones": {}}

    def zone(self, zone_id: str) -> ZoneState:
        """Return the state of `zone_id`, creating it if needed."""
        return self._data["zones"].setdefault(zone_id, _empty_zone())

    def zone_ids(self) -> list[str]:
        """Return the ids of all zones with persisted state."""
        return list(self._data["zones"])

    def prune_zones(self, valid_zone_ids: Iterable[str]) -> bool:
        """Drop state of zones that no longer exist. Return True if changed."""
        valid = set(valid_zone_ids)
        stale = [zone_id for zone_id in self._data["zones"] if zone_id not in valid]
        for zone_id in stale:
            del self._data["zones"][zone_id]
        return bool(stale)

    def prune_history(self, today: date) -> bool:
        """Drop day/irrigation records older than RETENTION_DAYS."""
        cutoff = today - timedelta(days=RETENTION_DAYS)
        changed = False
        for zone in self._data["zones"].values():
            days = [d for d in zone["days"] if date.fromisoformat(d["date"]) >= cutoff]
            irrigations = [
                record
                for record in zone["irrigations"]
                if datetime.fromisoformat(record["timestamp"]).date() >= cutoff
            ]
            if len(days) != len(zone["days"]) or len(irrigations) != len(
                zone["irrigations"]
            ):
                zone["days"] = days
                zone["irrigations"] = irrigations
                changed = True
        return changed

    def async_schedule_save(self) -> None:
        """Schedule a debounced save of the current document."""
        self._store.async_delay_save(self._snapshot, SAVE_DELAY_SECONDS)

    async def async_save(self) -> None:
        """Save the current document immediately."""
        await self._store.async_save(self._snapshot())

    async def async_remove(self) -> None:
        """Delete the persisted file (used when the config entry is removed)."""
        await self._store.async_remove()

    def _snapshot(self) -> StoredData:
        return self._data
