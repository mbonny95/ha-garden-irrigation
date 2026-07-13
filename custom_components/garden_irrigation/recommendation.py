"""Recommendation engine for garden_irrigation.

Milestone 7 scope only: an explainable irrigation recommendation per zone,
built from data already produced by weather.py/et0.py/balance.py/
irrigation_log.py. This module NEVER actuates hardware and NEVER records or
schedules anything - it only computes a read-only, explainable suggestion
(reasons/limits_applied/warnings plus recommended mm/per-source minutes/block
plan) for later consumption. Exposing it as its own sensor entities is out of
scope here (sensor.py may not be touched in M7); it is exposed via
`coordinator.data["recommendation"]` for a later milestone to build on, the
same way M3's et0/M4's balance were exposed before M5 built sensors for them.

Two variants are built on every call:
  - `final`: derived from the REAL, persisted balance for the most recently
    completed day (balance.py's ZoneBalanceResult) - this is what "sticks"
    for the day, per CLAUDE.md's once-per-day 05:30 finalization.
  - `preview`: a read-only PROJECTION of "if today ended right now", computed
    from the current persisted deficit plus today's in-progress ET0/rain/
    irrigation. It never calls balance.py's process_daily_balance and is
    never persisted, so it can be freely recomputed on every refresh without
    any risk of double-counting - CLAUDE.md's 20:00 preview is exactly this;
    scheduler.py only guarantees a refresh happens at 20:00/05:30, the
    preview/final distinction lives entirely here.

Limits considered (never silently invented, all from already-existing data):
  - deficit vs RAW/TAW (balance.py)
  - the sliding 7-day recorded-irrigation cap (balance.py)
  - the minimum 48h interval since the last recorded irrigation for the zone
    (irrigation_log.py)
  - WH51 soil moisture as a soft, explainable corroborating signal only
    (device-relative, diagnostic-only for the first DEFAULT_CALIBRATION_DAYS
    days - see CLAUDE.md §1.9). It NEVER blocks or overrides the
    deficit-based decision, only annotates it with a reason/warning.

Calibration window: since the manual start/end-calibration action is a later
milestone (M9's select/button), the 14-day window here starts automatically
at the first valid WH51 reading ever observed for that zone (persisted).
A future M9 action can supersede this marker without any migration, since it
is just another timestamp in the same store.

No automatic fallback: if the underlying balance for a day could not be
applied (ET0 unavailable) or hasn't been computed at all yet (pending), or if
today's in-progress ET0 is itself incomplete for the preview, the
recommendation for that variant is `ready=False` with no invented numbers.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .balance import SKIPPED_ALREADY_PROCESSED, BalanceEngine, ZoneBalanceResult
from .const import (
    CONF_ZONE1_AREA_M2,
    CONF_ZONE1_MM_PER_MIN_MAINS,
    CONF_ZONE1_MM_PER_MIN_TANK,
    CONF_ZONE1_SOIL_MOISTURE_ENTITY,
    CONF_ZONE2_AREA_M2,
    CONF_ZONE2_MM_PER_MIN_MAINS,
    CONF_ZONE2_MM_PER_MIN_TANK,
    CONF_ZONE2_SOIL_MOISTURE_ENTITY,
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
    DEFAULT_WH51_CRITICAL_THRESHOLD,
    DEFAULT_WH51_DRY_THRESHOLD,
    DEFAULT_WH51_WET_THRESHOLD,
    SOURCE_MAINS_WATER,
    SOURCES,
    STORAGE_KEY_RECOMMENDATION,
    ZONE_1,
    ZONES,
)
from .irrigation_log import IrrigationLog
from .storage import GardenIrrigationStore

_LOGGER = logging.getLogger(__name__)

SAVE_DELAY_SECONDS = 5

WH51_STATUS_UNAVAILABLE = "unavailable"
WH51_STATUS_DIAGNOSTIC = "diagnostic"
WH51_STATUS_CRITICAL = "critical"
WH51_STATUS_DRY = "dry"
WH51_STATUS_MODERATE = "moderate"
WH51_STATUS_WET = "wet"

REASON_NOT_READY_PENDING = "balance_not_yet_available"
REASON_NOT_READY_ET0_UNAVAILABLE = "et0_unavailable"
REASON_NOT_READY_PREVIEW_ET0_UNAVAILABLE = "et0_unavailable_today"
REASON_DEFICIT_BELOW_RAW = "deficit_below_raw"
REASON_DEFICIT_AT_OR_ABOVE_RAW = "deficit_at_or_above_raw"
REASON_WH51_CORROBORATES = "wh51_corroborates"
REASON_WH51_CONTRADICTS = "wh51_contradicts"

LIMIT_MIN_INTERVAL_NOT_ELAPSED = "min_interval_not_elapsed"
LIMIT_WEEKLY_CAP_REACHED = "weekly_cap_reached"
LIMIT_WEEKLY_CAP_PARTIAL = "weekly_cap_partial"


def _mm_per_minute(entry: ConfigEntry, zone_id: str, source: str) -> float | None:
    """Return the configured mm/minute for `zone_id`+`source`, or None if unset.

    Deliberately re-implemented here (not imported from irrigation_log.py,
    out of scope to touch in M7): same const.py keys, same nullable-tank
    semantics.
    """
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


def _soil_moisture_entity_id(entry: ConfigEntry, zone_id: str) -> str:
    """Return the configured WH51 soil-moisture entity_id for `zone_id`."""
    key = (
        CONF_ZONE1_SOIL_MOISTURE_ENTITY
        if zone_id == ZONE_1
        else CONF_ZONE2_SOIL_MOISTURE_ENTITY
    )
    return str(entry.data[key])


def _current_taw_raw_mm() -> tuple[float, float]:
    """TAW/RAW from the same config-derived constants balance.py's
    ZoneAgronomyParams defaults to (no per-zone override exists yet)."""
    taw_mm = (DEFAULT_ROOT_DEPTH_MM / 1000.0) * DEFAULT_AWC_MM_PER_M
    return taw_mm, taw_mm * DEFAULT_P_DEPLETION_FRACTION


def _block_plan(minutes: float) -> tuple[BlockPlanEntry, ...]:
    """Split `minutes` into <=DEFAULT_MAX_CYCLE_MINUTES-minute blocks, with a
    pause between (never after) consecutive blocks."""
    if minutes <= 0:
        return ()
    blocks: list[BlockPlanEntry] = []
    remaining = minutes
    while remaining > 0:
        block_minutes = min(remaining, DEFAULT_MAX_CYCLE_MINUTES)
        remaining -= block_minutes
        pause = DEFAULT_BLOCK_PAUSE_MINUTES if remaining > 0 else 0.0
        blocks.append(BlockPlanEntry(minutes=block_minutes, pause_after_minutes=pause))
    return tuple(blocks)


@dataclass(frozen=True)
class BlockPlanEntry:
    """One block of a possibly multi-block recommended cycle."""

    minutes: float
    pause_after_minutes: float  # 0 for the last block


@dataclass(frozen=True)
class SourceRecommendation:
    """Per-source (mm/minute-dependent) view of the recommended amount."""

    source: str
    calibrated: bool
    minutes: float | None
    blocks: tuple[BlockPlanEntry, ...]


@dataclass(frozen=True)
class ZoneRecommendationResult:
    """One explainable, read-only recommendation for a single zone."""

    zone_id: str
    preview: bool
    ready: bool
    reasons: tuple[str, ...]
    limits_applied: tuple[str, ...]
    warnings: tuple[str, ...]
    deficit_mm: float | None
    raw_mm: float | None
    taw_mm: float | None
    needs_irrigation: bool | None
    recommended_mm: float | None
    estimated_liters: float | None
    sources: Mapping[str, SourceRecommendation]
    wh51_status: str
    wh51_percent: float | None
    wh51_calibrated: bool


@dataclass(frozen=True)
class ZoneRecommendationBundle:
    """The final (persisted-balance-based) and preview (projected) results."""

    final: ZoneRecommendationResult
    preview: ZoneRecommendationResult


@dataclass(frozen=True)
class _Wh51CalibrationState:
    """Per-zone WH51 calibration baseline (device-relative, not VWC)."""

    first_seen: datetime | None
    baseline_min: float | None
    baseline_max: float | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for Store persistence."""
        return {
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "baseline_min": self.baseline_min,
            "baseline_max": self.baseline_max,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> _Wh51CalibrationState:
        """Restore from a previously persisted dict (see to_dict)."""
        first_seen_raw = data.get("first_seen")
        first_seen = dt_util.parse_datetime(first_seen_raw) if first_seen_raw else None
        return cls(
            first_seen=first_seen,
            baseline_min=data.get("baseline_min"),
            baseline_max=data.get("baseline_max"),
        )


def _classify_wh51(
    calibration: _Wh51CalibrationState, percent: float | None, now: datetime
) -> tuple[str, bool]:
    """Return (status, calibrated) for one WH51 reading given its baseline."""
    if percent is None:
        return WH51_STATUS_UNAVAILABLE, False

    calibrated = (
        calibration.first_seen is not None
        and now >= calibration.first_seen + timedelta(days=DEFAULT_CALIBRATION_DAYS)
        and calibration.baseline_min is not None
        and calibration.baseline_max is not None
        and calibration.baseline_max > calibration.baseline_min
    )
    if not calibrated:
        return WH51_STATUS_DIAGNOSTIC, False

    assert calibration.baseline_min is not None
    assert calibration.baseline_max is not None
    position = (percent - calibration.baseline_min) / (
        calibration.baseline_max - calibration.baseline_min
    )
    position = max(0.0, min(1.0, position))
    if position <= DEFAULT_WH51_CRITICAL_THRESHOLD:
        return WH51_STATUS_CRITICAL, True
    if position <= DEFAULT_WH51_DRY_THRESHOLD:
        return WH51_STATUS_DRY, True
    if position >= DEFAULT_WH51_WET_THRESHOLD:
        return WH51_STATUS_WET, True
    return WH51_STATUS_MODERATE, True


class RecommendationEngine:
    """Builds explainable, read-only irrigation recommendations per zone.

    Not an entity: plain domain logic held by the coordinator
    (`coordinator.recommendation`). Never actuates anything and never records
    or persists a balance change itself - see balance.py/irrigation_log.py for
    the state actually mutated by other engines.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        balance: BalanceEngine,
        irrigation_log: IrrigationLog,
    ) -> None:
        """Build the engine with an empty WH51 calibration baseline."""
        self.hass = hass
        self._entry = entry
        self._balance = balance
        self._irrigation_log = irrigation_log
        self._store = GardenIrrigationStore(hass, STORAGE_KEY_RECOMMENDATION)
        self._calibration: dict[str, _Wh51CalibrationState] = {
            zone_id: _Wh51CalibrationState(None, None, None) for zone_id in ZONES
        }

    async def async_setup(self) -> None:
        """Restore the persisted WH51 calibration baseline."""
        stored = await self._store.async_load()
        wh51_data = stored.get("wh51", {})
        for zone_id in ZONES:
            if zdata := wh51_data.get(zone_id):
                self._calibration[zone_id] = _Wh51CalibrationState.from_dict(zdata)

    async def async_shutdown(self) -> None:
        """Force an immediate (non-debounced) persistence flush."""
        await self._store.async_save(self._save_data())

    def _read_wh51_percent(self, zone_id: str) -> float | None:
        entity_id = _soil_moisture_entity_id(self._entry, zone_id)
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    def _update_calibration(
        self, zone_id: str, percent: float | None, now: datetime
    ) -> _Wh51CalibrationState:
        """Widen the observed [min, max] baseline with the current reading.

        Sampled only when a recommendation is built (event-driven, like the
        rest of the coordinator) - not a continuous accumulator, so the
        baseline reflects the readings seen at refresh times, not a true
        continuous min/max. That is an accepted approximation, consistent
        with this integration's event-driven (not polling) architecture.
        """
        if percent is None:
            return self._calibration[zone_id]
        current = self._calibration[zone_id]
        first_seen = current.first_seen or now
        baseline_min = (
            percent
            if current.baseline_min is None
            else min(current.baseline_min, percent)
        )
        baseline_max = (
            percent
            if current.baseline_max is None
            else max(current.baseline_max, percent)
        )
        updated = _Wh51CalibrationState(first_seen, baseline_min, baseline_max)
        self._calibration[zone_id] = updated
        self._schedule_save()
        return updated

    def _last_irrigation_ts(self, zone_id: str) -> datetime | None:
        events = self._irrigation_log.events_for_zone(zone_id)
        if not events:
            return None
        return max(event.timestamp for event in events)

    def build(
        self,
        zone_id: str,
        balance_result: ZoneBalanceResult,
        today_et0_mm: float | None,
        today_rain_mm: float,
        now: datetime | None = None,
    ) -> ZoneRecommendationBundle:
        """Build both the final and preview recommendation for `zone_id`."""
        now = now or dt_util.now()
        percent = self._read_wh51_percent(zone_id)
        calibration = self._update_calibration(zone_id, percent, now)
        wh51_status, wh51_calibrated = _classify_wh51(calibration, percent, now)
        last_irrigation_ts = self._last_irrigation_ts(zone_id)

        final_ready = (
            balance_result.applied
            or balance_result.skipped_reason == SKIPPED_ALREADY_PROCESSED
        )
        final_not_ready_reason = None
        if not final_ready:
            final_not_ready_reason = (
                REASON_NOT_READY_ET0_UNAVAILABLE
                if balance_result.skipped_reason is not None
                else REASON_NOT_READY_PENDING
            )
        final = self._evaluate(
            zone_id=zone_id,
            preview=False,
            ready=final_ready,
            not_ready_reason=final_not_ready_reason,
            deficit_mm=balance_result.deficit_mm,
            taw_mm=balance_result.taw_mm,
            raw_mm=balance_result.raw_mm,
            irrigation_7d_mm=balance_result.irrigation_7d_mm,
            weekly_cap_mm=balance_result.weekly_cap_mm,
            last_irrigation_ts=last_irrigation_ts,
            wh51_status=wh51_status,
            wh51_percent=percent,
            wh51_calibrated=wh51_calibrated,
            now=now,
        )

        preview = self._build_preview(
            zone_id=zone_id,
            today_et0_mm=today_et0_mm,
            today_rain_mm=today_rain_mm,
            last_irrigation_ts=last_irrigation_ts,
            wh51_status=wh51_status,
            wh51_percent=percent,
            wh51_calibrated=wh51_calibrated,
            now=now,
        )

        return ZoneRecommendationBundle(final=final, preview=preview)

    def _build_preview(
        self,
        *,
        zone_id: str,
        today_et0_mm: float | None,
        today_rain_mm: float,
        last_irrigation_ts: datetime | None,
        wh51_status: str,
        wh51_percent: float | None,
        wh51_calibrated: bool,
        now: datetime,
    ) -> ZoneRecommendationResult:
        """Project "if today ended right now" without touching balance.py.

        Uses the SAME formulas as balance.py's process_daily_balance (ETc =
        ET0*Kc, eff_rain = min(rain*factor, prev_deficit+ETc), deficit
        clamped to [0, TAW]) applied to today's still-in-progress data, never
        calling balance.py's own persisting method - so this can be
        recomputed on every refresh with no double-counting risk by
        construction.
        """
        prev_deficit_mm = self._balance.current_deficit_mm(zone_id)
        taw_mm, raw_mm = _current_taw_raw_mm()
        irrigation_7d_mm = self._balance.weekly_irrigation_mm(zone_id, now)

        if today_et0_mm is None:
            return self._evaluate(
                zone_id=zone_id,
                preview=True,
                ready=False,
                not_ready_reason=REASON_NOT_READY_PREVIEW_ET0_UNAVAILABLE,
                deficit_mm=prev_deficit_mm,
                taw_mm=taw_mm,
                raw_mm=raw_mm,
                irrigation_7d_mm=irrigation_7d_mm,
                weekly_cap_mm=DEFAULT_WEEKLY_CAP_MM,
                last_irrigation_ts=last_irrigation_ts,
                wh51_status=wh51_status,
                wh51_percent=wh51_percent,
                wh51_calibrated=wh51_calibrated,
                now=now,
            )

        projected_etc_mm = today_et0_mm * DEFAULT_KC
        start_of_today = dt_util.start_of_local_day(now)
        irrigation_today_mm = self._irrigation_log.aggregate(
            zone_id, since=start_of_today, until=now
        ).mm
        eff_rain_mm = min(
            today_rain_mm * DEFAULT_RAIN_EFFECTIVE_FACTOR,
            prev_deficit_mm + projected_etc_mm,
        )
        projected_deficit_mm = min(
            max(
                prev_deficit_mm + projected_etc_mm - eff_rain_mm - irrigation_today_mm,
                0.0,
            ),
            taw_mm,
        )

        return self._evaluate(
            zone_id=zone_id,
            preview=True,
            ready=True,
            not_ready_reason=None,
            deficit_mm=projected_deficit_mm,
            taw_mm=taw_mm,
            raw_mm=raw_mm,
            irrigation_7d_mm=irrigation_7d_mm,
            weekly_cap_mm=DEFAULT_WEEKLY_CAP_MM,
            last_irrigation_ts=last_irrigation_ts,
            wh51_status=wh51_status,
            wh51_percent=wh51_percent,
            wh51_calibrated=wh51_calibrated,
            now=now,
        )

    def _evaluate(
        self,
        *,
        zone_id: str,
        preview: bool,
        ready: bool,
        not_ready_reason: str | None,
        deficit_mm: float,
        taw_mm: float,
        raw_mm: float,
        irrigation_7d_mm: float,
        weekly_cap_mm: float,
        last_irrigation_ts: datetime | None,
        wh51_status: str,
        wh51_percent: float | None,
        wh51_calibrated: bool,
        now: datetime,
    ) -> ZoneRecommendationResult:
        """Core decision logic, shared by the final and preview variants.

        Deficit/TAW/RAW are always reported (informational, and always
        derivable from already-known data) even when `ready` is False;
        needs_irrigation/recommended_mm/sources are only ever computed when
        `ready` is True - no invented numbers otherwise.
        """
        if not ready:
            return ZoneRecommendationResult(
                zone_id=zone_id,
                preview=preview,
                ready=False,
                reasons=(not_ready_reason,) if not_ready_reason else (),
                limits_applied=(),
                warnings=(),
                deficit_mm=deficit_mm,
                raw_mm=raw_mm,
                taw_mm=taw_mm,
                needs_irrigation=None,
                recommended_mm=None,
                estimated_liters=None,
                sources={},
                wh51_status=wh51_status,
                wh51_percent=wh51_percent,
                wh51_calibrated=wh51_calibrated,
            )

        reasons: list[str] = []
        limits_applied: list[str] = []
        warnings: list[str] = []

        raw_exceeded = deficit_mm >= raw_mm
        reasons.append(
            REASON_DEFICIT_AT_OR_ABOVE_RAW if raw_exceeded else REASON_DEFICIT_BELOW_RAW
        )

        min_interval_elapsed = last_irrigation_ts is None or (
            now - last_irrigation_ts
        ) >= timedelta(hours=DEFAULT_MIN_INTERVAL_HOURS)
        cap_remaining_mm = max(weekly_cap_mm - irrigation_7d_mm, 0.0)

        needs_irrigation = (
            raw_exceeded and min_interval_elapsed and cap_remaining_mm > 0
        )

        if raw_exceeded and not min_interval_elapsed:
            limits_applied.append(LIMIT_MIN_INTERVAL_NOT_ELAPSED)
        if raw_exceeded and cap_remaining_mm <= 0:
            limits_applied.append(LIMIT_WEEKLY_CAP_REACHED)

        if not raw_exceeded or not min_interval_elapsed:
            recommended_mm = 0.0
        else:
            recommended_mm = min(deficit_mm, cap_remaining_mm)
            if (
                recommended_mm < deficit_mm
                and LIMIT_WEEKLY_CAP_REACHED not in limits_applied
            ):
                limits_applied.append(LIMIT_WEEKLY_CAP_PARTIAL)

        # WH51: a soft, explainable corroborating signal only - it never
        # changes needs_irrigation/recommended_mm above, only annotates them.
        if wh51_calibrated:
            wh51_suggests_dry = wh51_status in (WH51_STATUS_CRITICAL, WH51_STATUS_DRY)
            wh51_suggests_wet = wh51_status == WH51_STATUS_WET
            if raw_exceeded and wh51_suggests_dry:
                reasons.append(REASON_WH51_CORROBORATES)
            elif raw_exceeded and wh51_suggests_wet:
                warnings.append(REASON_WH51_CONTRADICTS)
            elif not raw_exceeded and wh51_suggests_wet:
                reasons.append(REASON_WH51_CORROBORATES)
            elif not raw_exceeded and wh51_suggests_dry:
                warnings.append(REASON_WH51_CONTRADICTS)

        estimated_liters = recommended_mm * _area_m2(self._entry, zone_id)

        sources: dict[str, SourceRecommendation] = {}
        for source in SOURCES:
            mm_per_minute = _mm_per_minute(self._entry, zone_id, source)
            if mm_per_minute is None or mm_per_minute <= 0:
                sources[source] = SourceRecommendation(
                    source=source, calibrated=False, minutes=None, blocks=()
                )
                continue
            minutes = recommended_mm / mm_per_minute
            sources[source] = SourceRecommendation(
                source=source,
                calibrated=True,
                minutes=minutes,
                blocks=_block_plan(minutes),
            )

        return ZoneRecommendationResult(
            zone_id=zone_id,
            preview=preview,
            ready=True,
            reasons=tuple(reasons),
            limits_applied=tuple(limits_applied),
            warnings=tuple(warnings),
            deficit_mm=deficit_mm,
            raw_mm=raw_mm,
            taw_mm=taw_mm,
            needs_irrigation=needs_irrigation,
            recommended_mm=recommended_mm,
            estimated_liters=estimated_liters,
            sources=sources,
            wh51_status=wh51_status,
            wh51_percent=wh51_percent,
            wh51_calibrated=wh51_calibrated,
        )

    def _save_data(self) -> dict[str, Any]:
        return {
            "wh51": {zone_id: self._calibration[zone_id].to_dict() for zone_id in ZONES}
        }

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._save_data, SAVE_DELAY_SECONDS)
