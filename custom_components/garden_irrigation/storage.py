"""Persistence skeleton for garden_irrigation.

Milestone 1 only wraps `helpers.storage.Store`; no domain logic (weather
accumulators, deficit, event log) lives here yet — see weather.py, balance.py
and irrigation_log.py in later milestones.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
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
        """Persist data immediately (atomic write via Store)."""
        await self._store.async_save(data)
