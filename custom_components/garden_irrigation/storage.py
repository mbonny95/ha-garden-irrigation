"""Persistence wrapper for garden_irrigation.

Wraps `helpers.storage.Store`. Domain logic (weather accumulators here in
Milestone 2; per-zone deficit and event log in later milestones) lives in
weather.py/balance.py/irrigation_log.py, not here — this module only owns the
versioned, debounced read/write mechanics.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

STORAGE_VERSION = 1


class GardenIrrigationStore:
    """Thin async wrapper around a versioned, debounced Store file."""

    def __init__(self, hass: HomeAssistant, key: str) -> None:
        """Create a store bound to `key` (e.g. "garden_irrigation.state")."""
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, key)

    async def async_load(self) -> dict[str, Any]:
        """Load persisted data, or an empty dict if nothing was saved yet."""
        data = await self._store.async_load()
        return data or {}

    async def async_save(self, data: dict[str, Any]) -> None:
        """Persist data immediately (atomic write via Store).

        Used for forced flushes (midnight roll, unload, consolidation) where
        the write must not be coalesced away by a pending debounced save.
        """
        await self._store.async_save(data)

    @callback
    def async_delay_save(
        self, data_func: Callable[[], dict[str, Any]], delay: float = 0
    ) -> None:
        """Schedule a debounced save; used for high-frequency live updates.

        `data_func` is called at write time (not now), so callers can pass a
        method that reads current in-memory state rather than a snapshot
        that might go stale before the delay elapses.
        """
        self._store.async_delay_save(data_func, delay)
