"""Manual irrigation-cycle recording and persistence for garden_irrigation.

Milestone 6 scope only: the `garden_irrigation.record_irrigation` service, the
persisted event log (365-day retention, its own Store), and per-source
aggregates derived on demand from that log. No recommendation/scheduling
logic happens here - see recommendation.py / scheduler.py.

Idempotency: every event carries an id (a client-supplied `idempotency_key`,
or an auto-generated UUID if none was given). A repeat call with the same
idempotency_key is a pure no-op - the existing event is returned unchanged
and the balance is NOT touched again. This is a *recording-layer* guard
against double-submission (e.g. a retried service call); it is independent of
- but complements - balance.py's own once-per-day idempotency for the daily
deficit calculation.

Calibration: mm/liters are only computable when the config entry declares a
mm_per_minute for that zone/source pair (mains water always has one; the
rainwater tank may be left uncalibrated - see const.py). When uncalibrated,
the raw event (minutes/source/timestamp/notes) is still persisted, but
mm/liters are None and the zone's water-balance deficit is NOT decremented -
CLAUDE.md forbids inventing a default calibration.

Timestamps are always `dt_util.now()` at call time - there is no backdating
field in the service schema, so this is enforced structurally, not just by
convention.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ZONE1_AREA_M2,
    CONF_ZONE1_MM_PER_MIN_MAINS,
    CONF_ZONE1_MM_PER_MIN_TANK,
    CONF_ZONE2_AREA_M2,
    CONF_ZONE2_MM_PER_MIN_MAINS,
    CONF_ZONE2_MM_PER_MIN_TANK,
    DEFAULT_MAX_CYCLE_MINUTES,
    DOMAIN,
    SOURCE_MAINS_WATER,
    SOURCES,
    STORAGE_KEY_EVENTS,
    ZONE_1,
    ZONES,
)
from .storage import GardenIrrigationStore

if TYPE_CHECKING:
    from .coordinator import GardenIrrigationCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_RECORD_IRRIGATION = "record_irrigation"
SAVE_DELAY_SECONDS = 5
EVENT_RETENTION_DAYS = 365

RECORD_IRRIGATION_SCHEMA = vol.Schema(
    {
        vol.Required("zone"): vol.In(ZONES),
        vol.Required("source"): vol.In(SOURCES),
        vol.Required("duration_minutes"): vol.All(
            vol.Coerce(float),
            vol.Range(min=0, min_included=False, max=DEFAULT_MAX_CYCLE_MINUTES),
        ),
        vol.Optional("notes"): cv.string,
        vol.Optional("idempotency_key"): cv.string,
    }
)


def _mm_per_minute(entry: ConfigEntry, zone_id: str, source: str) -> float | None:
    """Return the configured mm/minute for `zone_id`+`source`, or None if unset."""
    if zone_id == ZONE_1:
        key = (
            CONF_ZONE1_MM_PER_MIN_MAINS
            if source == SOURCE_MAINS_WATER
            else CONF_ZONE1_MM_PER_MIN_TANK
        )
    else:
        key = (
            CONF_ZONE2_MM_PER_MIN_MAINS
            if source == SOURCE_MAINS_WATER
            else CONF_ZONE2_MM_PER_MIN_TANK
        )
    value = entry.data.get(key)
    return float(value) if value is not None else None


def _area_m2(entry: ConfigEntry, zone_id: str) -> float:
    """Return the configured area for `zone_id` in square meters."""
    key = CONF_ZONE1_AREA_M2 if zone_id == ZONE_1 else CONF_ZONE2_AREA_M2
    return float(entry.data[key])


@dataclass(frozen=True)
class IrrigationEvent:
    """One persisted, user-recorded irrigation cycle."""

    id: str
    zone_id: str
    source: str
    timestamp: datetime
    duration_minutes: float
    calibrated: bool
    mm: float | None
    liters: float | None
    notes: str | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for Store persistence."""
        return {
            "id": self.id,
            "zone_id": self.zone_id,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "duration_minutes": self.duration_minutes,
            "calibrated": self.calibrated,
            "mm": self.mm,
            "liters": self.liters,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> IrrigationEvent:
        """Restore from a previously persisted dict (see to_dict)."""
        timestamp = dt_util.parse_datetime(data["timestamp"])
        assert timestamp is not None
        return cls(
            id=data["id"],
            zone_id=data["zone_id"],
            source=data["source"],
            timestamp=timestamp,
            duration_minutes=float(data["duration_minutes"]),
            calibrated=bool(data["calibrated"]),
            mm=data.get("mm"),
            liters=data.get("liters"),
            notes=data.get("notes"),
        )


@dataclass(frozen=True)
class IrrigationAggregate:
    """A derived (never persisted) sum over a subset of the event log."""

    count: int
    mm: float
    liters: float


class IrrigationLog:
    """Owns the manual-cycle event log and the `record_irrigation` service.

    Not an entity: plain domain logic held by the coordinator
    (`coordinator.irrigation_log`). Aggregates (`aggregate`/`totals_by_source`)
    are always derived on demand from the persisted event list, never
    maintained as separate running counters.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: GardenIrrigationCoordinator,
    ) -> None:
        """Build the log with an empty event list; nothing is persisted yet."""
        self.hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._store = GardenIrrigationStore(hass, STORAGE_KEY_EVENTS)
        self._events: list[IrrigationEvent] = []

    async def async_setup(self) -> None:
        """Restore persisted events and register the recording service."""
        stored = await self._store.async_load()
        self._events = [
            IrrigationEvent.from_dict(item) for item in stored.get("events", [])
        ]
        self._prune(dt_util.now())

        if not self.hass.services.has_service(DOMAIN, SERVICE_RECORD_IRRIGATION):
            self.hass.services.async_register(
                DOMAIN,
                SERVICE_RECORD_IRRIGATION,
                self._async_handle_record_irrigation,
                schema=RECORD_IRRIGATION_SCHEMA,
            )

    async def async_shutdown(self) -> None:
        """Unregister the service and force an immediate persistence flush."""
        if self.hass.services.has_service(DOMAIN, SERVICE_RECORD_IRRIGATION):
            self.hass.services.async_remove(DOMAIN, SERVICE_RECORD_IRRIGATION)
        await self._store.async_save(self._save_data())

    async def _async_handle_record_irrigation(self, call: ServiceCall) -> None:
        await self.async_record_irrigation(
            zone_id=call.data["zone"],
            source=call.data["source"],
            duration_minutes=call.data["duration_minutes"],
            notes=call.data.get("notes"),
            idempotency_key=call.data.get("idempotency_key"),
        )

    async def async_record_irrigation(
        self,
        *,
        zone_id: str,
        source: str,
        duration_minutes: float,
        notes: str | None = None,
        idempotency_key: str | None = None,
    ) -> IrrigationEvent:
        """Record one manual irrigation cycle (current timestamp only).

        A repeat call with the same `idempotency_key` (or auto-generated id,
        for a genuinely identical retry) returns the original event unchanged
        without recording or decrementing anything a second time.
        """
        event_id = idempotency_key or str(uuid4())
        existing = self._find(event_id)
        if existing is not None:
            _LOGGER.info(
                "Duplicate record_irrigation call ignored (idempotency_key=%s)",
                event_id,
            )
            return existing

        timestamp = dt_util.now()
        mm_per_minute = _mm_per_minute(self._entry, zone_id, source)
        calibrated = mm_per_minute is not None
        mm = duration_minutes * mm_per_minute if mm_per_minute is not None else None
        liters = mm * _area_m2(self._entry, zone_id) if mm is not None else None

        event = IrrigationEvent(
            id=event_id,
            zone_id=zone_id,
            source=source,
            timestamp=timestamp,
            duration_minutes=duration_minutes,
            calibrated=calibrated,
            mm=mm,
            liters=liters,
            notes=notes,
        )
        self._events.append(event)
        self._prune(timestamp)

        if mm is not None:
            self._coordinator.balance.record_irrigation(zone_id, timestamp, mm)
        else:
            _LOGGER.warning(
                "Irrigation recorded for zone %s from an uncalibrated source "
                "(%s): the water-balance deficit was NOT updated (mm/liters "
                "unknown)",
                zone_id,
                source,
            )

        self._schedule_save()
        await self._coordinator.async_request_refresh()
        return event

    def _find(self, event_id: str) -> IrrigationEvent | None:
        for event in self._events:
            if event.id == event_id:
                return event
        return None

    def _prune(self, as_of: datetime) -> None:
        cutoff = as_of - timedelta(days=EVENT_RETENTION_DAYS)
        self._events = [event for event in self._events if event.timestamp >= cutoff]

    def events_for_zone(self, zone_id: str) -> list[IrrigationEvent]:
        """Return every retained event for `zone_id`, oldest first."""
        return [event for event in self._events if event.zone_id == zone_id]

    def aggregate(
        self,
        zone_id: str,
        *,
        source: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> IrrigationAggregate:
        """Derive count/mm/liters over the matching subset of the event log.

        mm/liters only sum calibrated events (uncalibrated ones still count
        toward `count`, since the cycle genuinely happened, just without a
        known mm/liters figure).
        """
        matching = [
            event
            for event in self._events
            if event.zone_id == zone_id
            and (source is None or event.source == source)
            and (since is None or event.timestamp >= since)
            and (until is None or event.timestamp <= until)
        ]
        return IrrigationAggregate(
            count=len(matching),
            mm=sum(event.mm for event in matching if event.mm is not None),
            liters=sum(event.liters for event in matching if event.liters is not None),
        )

    def totals_by_source(self, zone_id: str) -> dict[str, IrrigationAggregate]:
        """Per-source aggregate totals for `zone_id` (all retained events)."""
        return {source: self.aggregate(zone_id, source=source) for source in SOURCES}

    def _save_data(self) -> dict[str, Any]:
        return {"events": [event.to_dict() for event in self._events]}

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._save_data, SAVE_DELAY_SECONDS)
