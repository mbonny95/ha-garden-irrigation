"""Per-zone water balance engine for garden_irrigation.

Milestone 4 scope only: ETc, effective rain, the daily deficit balance, and
the sliding 7-day recorded-irrigation figure used for the weekly cap. No
recommendation/scheduling/notification happens here (see recommendation.py /
scheduler.py in later milestones); this module only maintains and reports the
per-zone deficit.

Formulas (CLAUDE.md, do not "simplify" away):
    ETc          = ET0 * Kc
    TAW          = (root_depth_mm/1000) * AWC_mm_per_m
    RAW          = TAW * p
    eff_rain     = min(daily_rain*factor, prev_deficit + ETc)
    new_deficit  = clamp(prev_deficit + ETc - eff_rain - irrigation_mm, 0, TAW)

The balance for a given local calendar day is applied at most once
(idempotent via a per-zone `last_balance_date` marker) - a second call for an
already-processed day is a no-op that simply reports the stored result. There
is no automatic fallback: if ET0 for that day is unknown/incomplete, the
balance is left untouched (not silently advanced with a guessed ETc) and the
day is NOT marked processed, so it can still be applied later if the data
becomes available.

Persistence uses its own Store file (`garden_irrigation.balance_state`), kept
separate from weather.py's `garden_irrigation.state` - see the comment on
`STORAGE_KEY_BALANCE` in const.py for why the two cannot safely share a file
without a change to weather.py's save/merge logic (out of scope for M4).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_AWC_MM_PER_M,
    DEFAULT_KC,
    DEFAULT_P_DEPLETION_FRACTION,
    DEFAULT_RAIN_EFFECTIVE_FACTOR,
    DEFAULT_ROOT_DEPTH_MM,
    DEFAULT_WEEKLY_CAP_MM,
    STORAGE_KEY_BALANCE,
    ZONES,
)
from .storage import GardenIrrigationStore

_LOGGER = logging.getLogger(__name__)

SAVE_DELAY_SECONDS = 5
# The daily balance only ever needs same-day and trailing-7-day irrigation
# sums; a small buffer beyond 7 days keeps the persisted ledger bounded
# without depending on irrigation_log.py's future 365-day retention.
IRRIGATION_LEDGER_RETENTION_DAYS = 8

SKIPPED_ALREADY_PROCESSED = "already_processed"
SKIPPED_ET0_UNAVAILABLE = "et0_unavailable"


@dataclass(frozen=True)
class ZoneAgronomyParams:
    """Per-zone agronomy parameters (options-flow configurable in a later milestone).

    Both zones use the same CLAUDE.md-documented defaults for now, since no
    options flow exposes per-zone overrides yet (const.py DEFAULT_* values).
    """

    kc: float = DEFAULT_KC
    root_depth_mm: float = DEFAULT_ROOT_DEPTH_MM
    awc_mm_per_m: float = DEFAULT_AWC_MM_PER_M
    p_depletion_fraction: float = DEFAULT_P_DEPLETION_FRACTION
    rain_effective_factor: float = DEFAULT_RAIN_EFFECTIVE_FACTOR
    weekly_cap_mm: float = DEFAULT_WEEKLY_CAP_MM

    @property
    def taw_mm(self) -> float:
        """Total Available Water [mm]."""
        return (self.root_depth_mm / 1000.0) * self.awc_mm_per_m

    @property
    def raw_mm(self) -> float:
        """Readily Available Water [mm]."""
        return self.taw_mm * self.p_depletion_fraction


@dataclass(frozen=True)
class ZoneBalanceResult:
    """Outcome of one `process_daily_balance` call for a single zone/day."""

    zone_id: str
    day: date
    applied: bool
    skipped_reason: str | None
    etc_mm: float | None
    eff_rain_mm: float | None
    irrigation_mm: float
    deficit_mm: float
    taw_mm: float
    raw_mm: float
    irrigation_7d_mm: float
    weekly_cap_mm: float
    weekly_cap_reached: bool


@dataclass(frozen=True)
class _IrrigationRecord:
    """One user-recorded irrigation entry (mm already converted from minutes).

    Milestone 4 provides the ledger/cap mechanics only; the actual recording
    action (`garden_irrigation.record_irrigation`) is irrigation_log.py's job
    in a later milestone. `record_irrigation` here is the engine-level API
    that milestone will call into.
    """

    timestamp: datetime
    mm: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize for Store persistence."""
        return {"timestamp": self.timestamp.isoformat(), "mm": self.mm}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> _IrrigationRecord:
        """Restore from a previously persisted dict (see to_dict)."""
        timestamp = dt_util.parse_datetime(data["timestamp"])
        assert timestamp is not None
        return cls(timestamp=timestamp, mm=float(data["mm"]))


def _local_day_bounds(day: date) -> tuple[datetime, datetime]:
    """Local [00:00:00.000000, 23:59:59.999999] bounds for a calendar day."""
    start = dt_util.start_of_local_day(day)
    end = dt_util.as_local(datetime.combine(day, time.max))
    return start, end


class BalanceEngine:
    """Owns the per-zone water balance for one config entry.

    Not an entity: plain domain logic held by the coordinator
    (`coordinator.balance`). Driven by explicit `process_daily_balance` calls
    (no scheduler-driven 20:00/05:30 timing yet - see scheduler.py in a later
    milestone); calling it more than once for the same zone/day is safe and
    idempotent.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        params: Mapping[str, ZoneAgronomyParams] | None = None,
    ) -> None:
        """Build the engine with per-zone deficit/ledger starting empty."""
        self.hass = hass
        self._entry = entry
        self._store = GardenIrrigationStore(hass, STORAGE_KEY_BALANCE)
        self._params: dict[str, ZoneAgronomyParams] = dict(
            params or {zone_id: ZoneAgronomyParams() for zone_id in ZONES}
        )

        self._deficit: dict[str, float] = dict.fromkeys(ZONES, 0.0)
        self._last_balance_date: dict[str, date | None] = dict.fromkeys(ZONES, None)
        self._irrigation: dict[str, list[_IrrigationRecord]] = {
            zone_id: [] for zone_id in ZONES
        }
        # ETc/effective-rain terms from the last successfully applied day,
        # for `_unchanged_result` to keep reporting on every later refresh of
        # the same already-processed day (persisted, not just RAM-cached -
        # see `_save_data`/`async_setup` below). `irrigation_mm` needs no
        # such cache: it's always freshly derivable from `self._irrigation`,
        # which is already persisted on its own.
        self._last_applied_terms: dict[str, dict[str, float] | None] = dict.fromkeys(
            ZONES, None
        )

    async def async_setup(self) -> None:
        """Restore persisted deficit/last-balance-date/irrigation ledger."""
        stored = await self._store.async_load()
        for zone_id in ZONES:
            zone_data = stored.get("zones", {}).get(zone_id)
            if zone_data:
                self._deficit[zone_id] = float(zone_data.get("deficit_mm", 0.0))
                last_date_raw = zone_data.get("last_balance_date")
                self._last_balance_date[zone_id] = (
                    date.fromisoformat(last_date_raw) if last_date_raw else None
                )
            irrigation_data = stored.get("irrigation", {}).get(zone_id, [])
            self._irrigation[zone_id] = [
                _IrrigationRecord.from_dict(item) for item in irrigation_data
            ]
            self._last_applied_terms[zone_id] = stored.get(
                "last_applied_terms", {}
            ).get(zone_id)

    async def async_shutdown(self) -> None:
        """Force an immediate (non-debounced) persistence flush."""
        await self._async_force_flush()

    def current_deficit_mm(self, zone_id: str) -> float:
        """Return the currently stored deficit for `zone_id`, unmodified."""
        return self._deficit[zone_id]

    def record_irrigation(self, zone_id: str, timestamp: datetime, mm: float) -> None:
        """Append one recorded irrigation entry (engine-level API; see class docstring).

        Pruning is anchored to `timestamp` itself (the entry's own recorded
        time), not wall-clock "now": every real caller records with the
        current instant anyway (no backdating - see CLAUDE.md), so the two
        coincide in production, but anchoring to `timestamp` keeps this
        deterministic under frozen-time tests.
        """
        self._irrigation[zone_id].append(_IrrigationRecord(timestamp, mm))
        self._prune_irrigation(zone_id, timestamp)
        self._schedule_save()

    def _prune_irrigation(self, zone_id: str, as_of: datetime) -> None:
        cutoff = as_of - timedelta(days=IRRIGATION_LEDGER_RETENTION_DAYS)
        self._irrigation[zone_id] = [
            record for record in self._irrigation[zone_id] if record.timestamp >= cutoff
        ]

    def _irrigation_mm_between(
        self, zone_id: str, start: datetime, end: datetime
    ) -> float:
        return sum(
            record.mm
            for record in self._irrigation[zone_id]
            if start <= record.timestamp <= end
        )

    def weekly_irrigation_mm(self, zone_id: str, as_of: datetime) -> float:
        """Sum of recorded irrigation over the trailing sliding 7x24h window.

        `as_of` is deliberately a caller-supplied instant, not derived from
        any `day` this engine is processing: the weekly cap is a genuinely
        different concept from the daily balance (see CLAUDE.md - "finestra
        mobile 7x24h", not a calendar week and not tied to the completed-day
        finalization). Callers reporting the *current* cap state must pass
        `dt_util.now()`, never a day's `day_end` - see `_unchanged_result`/
        `process_daily_balance` below, where passing `day_end` (the last
        *finalized* day's end) used to silently exclude same-day recordings
        from the cap until the next 05:30 rollover.
        """
        return self._irrigation_mm_between(zone_id, as_of - timedelta(days=7), as_of)

    def _unchanged_result(
        self, zone_id: str, day: date, skipped_reason: str | None
    ) -> ZoneBalanceResult:
        """Report current stored state for `day` without mutating anything.

        When `day` was genuinely already applied (`SKIPPED_ALREADY_PROCESSED`
        - guaranteed by the caller to be the same `day` `_last_applied_terms`
        was cached for, since both are set together in `process_daily_balance`),
        `etc_mm`/`eff_rain_mm` come from that cache - otherwise (pending, or
        ET0 was unavailable) they stay `None`, never fabricated.
        """
        params = self._params[zone_id]
        day_start, day_end = _local_day_bounds(day)
        irrigation_7d_mm = self.weekly_irrigation_mm(zone_id, dt_util.now())
        terms = (
            self._last_applied_terms[zone_id]
            if skipped_reason == SKIPPED_ALREADY_PROCESSED
            else None
        )
        return ZoneBalanceResult(
            zone_id=zone_id,
            day=day,
            applied=False,
            skipped_reason=skipped_reason,
            etc_mm=terms["etc_mm"] if terms else None,
            eff_rain_mm=terms["eff_rain_mm"] if terms else None,
            irrigation_mm=self._irrigation_mm_between(zone_id, day_start, day_end),
            deficit_mm=self._deficit[zone_id],
            taw_mm=params.taw_mm,
            raw_mm=params.raw_mm,
            irrigation_7d_mm=irrigation_7d_mm,
            weekly_cap_mm=params.weekly_cap_mm,
            weekly_cap_reached=irrigation_7d_mm >= params.weekly_cap_mm,
        )

    def pending_result(self, zone_id: str, day: date) -> ZoneBalanceResult:
        """Report current state for `day` without attempting to process it.

        Use this instead of `process_daily_balance` when `day`'s weather data
        isn't finalized yet (e.g. no completed local day exists so soon after
        setup) - it reports the same shape without logging the "ET0
        unavailable" warning that `process_daily_balance(..., et0_mm=None)`
        would, which would be misleading for a day that simply hasn't
        happened yet rather than one with genuinely missing sensor data.
        """
        return self._unchanged_result(zone_id, day, skipped_reason=None)

    def process_daily_balance(
        self,
        zone_id: str,
        day: date,
        et0_mm: float | None,
        rain_mm: float,
    ) -> ZoneBalanceResult:
        """Apply (once, idempotently) the completed day's balance for one zone.

        `et0_mm=None` signals ET0 was unknown/incomplete for `day`: per
        CLAUDE.md, there is no automatic fallback, so the deficit is left
        untouched and `day` is NOT marked processed (a later, better-informed
        call for the same day can still apply it).

        A repeat call for a `day` that was already successfully applied is a
        pure no-op (double-processing protection): it neither recomputes nor
        mutates the deficit, and reports `applied=False`, regardless of
        whether this is the same engine instance or one that reloaded the
        persisted `last_balance_date` after a restart.
        """
        if self._last_balance_date.get(zone_id) == day:
            return self._unchanged_result(zone_id, day, SKIPPED_ALREADY_PROCESSED)

        if et0_mm is None:
            _LOGGER.warning(
                "Water balance not applied for zone %s on %s: ET0 unavailable",
                zone_id,
                day.isoformat(),
            )
            return self._unchanged_result(zone_id, day, SKIPPED_ET0_UNAVAILABLE)

        params = self._params[zone_id]
        day_start, day_end = _local_day_bounds(day)
        prev_deficit = self._deficit[zone_id]
        etc_mm = et0_mm * params.kc
        irrigation_mm = self._irrigation_mm_between(zone_id, day_start, day_end)
        eff_rain_mm = min(rain_mm * params.rain_effective_factor, prev_deficit + etc_mm)
        new_deficit = min(
            max(prev_deficit + etc_mm - eff_rain_mm - irrigation_mm, 0.0),
            params.taw_mm,
        )

        self._deficit[zone_id] = new_deficit
        self._last_balance_date[zone_id] = day
        # Cached so `_unchanged_result` can keep reporting these on every
        # later refresh of this same already-processed day, instead of
        # reverting to None (the bug this cache fixes - see its own
        # declaration in __init__ for the full explanation).
        self._last_applied_terms[zone_id] = {
            "etc_mm": etc_mm,
            "eff_rain_mm": eff_rain_mm,
        }
        # Weekly cap: anchored to *now*, deliberately not to `day_end` above
        # (which only ever advances once/day, at the 05:30 finalization) -
        # see weekly_irrigation_mm's docstring.
        irrigation_7d_mm = self.weekly_irrigation_mm(zone_id, dt_util.now())
        result = ZoneBalanceResult(
            zone_id=zone_id,
            day=day,
            applied=True,
            skipped_reason=None,
            etc_mm=etc_mm,
            eff_rain_mm=eff_rain_mm,
            irrigation_mm=irrigation_mm,
            deficit_mm=new_deficit,
            taw_mm=params.taw_mm,
            raw_mm=params.raw_mm,
            irrigation_7d_mm=irrigation_7d_mm,
            weekly_cap_mm=params.weekly_cap_mm,
            weekly_cap_reached=irrigation_7d_mm >= params.weekly_cap_mm,
        )
        self._schedule_save()
        return result

    def _save_data(self) -> dict[str, Any]:
        def _last_balance_date_iso(zone_id: str) -> str | None:
            last_date = self._last_balance_date[zone_id]
            return last_date.isoformat() if last_date is not None else None

        return {
            "zones": {
                zone_id: {
                    "deficit_mm": self._deficit[zone_id],
                    "last_balance_date": _last_balance_date_iso(zone_id),
                }
                for zone_id in ZONES
            },
            "irrigation": {
                zone_id: [record.to_dict() for record in self._irrigation[zone_id]]
                for zone_id in ZONES
            },
            "last_applied_terms": {
                zone_id: self._last_applied_terms[zone_id]
                for zone_id in ZONES
                if self._last_applied_terms[zone_id] is not None
            },
        }

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._save_data, SAVE_DELAY_SECONDS)

    async def _async_force_flush(self) -> None:
        await self._store.async_save(self._save_data())
