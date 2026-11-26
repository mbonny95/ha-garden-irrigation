"""Explainable irrigation recommendation for one zone.

Pure function of the zone's current state. Limits (minimum interval, weekly
amount, soil moisture sensor, forecast rain) only add warnings: they never
change the amount or the decision. Every amount is an estimate.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Reason(StrEnum):
    """Why the decision is what it is."""

    DEFICIT_UNKNOWN = "deficit_unknown"
    DEFICIT_BELOW_RAW = "deficit_below_raw"
    DEFICIT_REACHED_RAW = "deficit_reached_raw"


class Advisory(StrEnum):
    """Advisory conditions shown next to the recommendation."""

    MIN_INTERVAL = "min_interval"
    WEEKLY_CAP = "weekly_cap"
    SOIL_SENSOR_WET = "soil_sensor_wet"
    SOIL_SENSOR_DRY = "soil_sensor_dry"
    RAIN_FORECAST = "rain_forecast"
    NO_SOURCE_RATE = "no_source_rate"


@dataclass(frozen=True, slots=True)
class Message:
    """A reason or warning code with the values that explain it."""

    code: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SoilSensorReading:
    """Current soil moisture reading and the user's own thresholds (%)."""

    value_pct: float
    dry_pct: float | None
    wet_pct: float | None


@dataclass(frozen=True, slots=True)
class ZoneState:
    """Everything the recommendation depends on."""

    deficit_mm: float | None
    raw_mm: float
    area_m2: float
    source_rates_mm_per_min: Mapping[str, float]  # only sources with a rate
    max_block_mm: float
    block_pause_min: float
    now: datetime
    last_irrigation: datetime | None = None
    min_interval_h: float | None = None
    irrigation_7d_mm: float = 0.0
    weekly_cap_mm: float | None = None
    soil_sensor: SoilSensorReading | None = None
    forecast_rain_mm: float | None = None
    forecast_threshold_mm: float = 0.0


@dataclass(frozen=True, slots=True)
class SourcePlan:
    """How to deliver the recommended amount with one water source."""

    total_minutes: float
    block_minutes: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Decision, amount and explanation for one zone."""

    needs_irrigation: bool | None  # None when the deficit is unknown
    amount_mm: float
    liters: float
    blocks_mm: tuple[float, ...]
    block_pause_min: float
    sources: dict[str, SourcePlan]
    reasons: tuple[Message, ...]
    warnings: tuple[Message, ...]


def split_blocks(amount_mm: float, max_block_mm: float) -> tuple[float, ...]:
    """Split an amount into the fewest equal blocks of at most max_block_mm."""
    if amount_mm <= 0:
        return ()
    count = max(math.ceil(amount_mm / max_block_mm - 1e-9), 1)
    return (amount_mm / count,) * count


def recommend(state: ZoneState) -> Recommendation:
    """Build the recommendation for one zone."""
    if state.deficit_mm is None:
        return Recommendation(
            needs_irrigation=None,
            amount_mm=0.0,
            liters=0.0,
            blocks_mm=(),
            block_pause_min=state.block_pause_min,
            sources={},
            reasons=(Message(Reason.DEFICIT_UNKNOWN),),
            warnings=(),
        )

    deficit = state.deficit_mm
    needs = deficit >= state.raw_mm
    params = {"deficit_mm": deficit, "raw_mm": state.raw_mm}
    reason = Message(
        Reason.DEFICIT_REACHED_RAW if needs else Reason.DEFICIT_BELOW_RAW, params
    )

    amount = deficit if needs else 0.0
    blocks = split_blocks(amount, state.max_block_mm)
    sources = {
        source: SourcePlan(
            total_minutes=amount / rate,
            block_minutes=tuple(block / rate for block in blocks),
        )
        for source, rate in state.source_rates_mm_per_min.items()
        if rate > 0
    }

    return Recommendation(
        needs_irrigation=needs,
        amount_mm=amount,
        liters=amount * state.area_m2,  # 1 mm over 1 m² = 1 L
        blocks_mm=blocks,
        block_pause_min=state.block_pause_min,
        sources=sources,
        reasons=(reason,),
        warnings=tuple(_warnings(state, needs, amount, bool(sources))),
    )


def _warnings(
    state: ZoneState, needs: bool, amount_mm: float, has_source: bool
) -> list[Message]:
    warnings: list[Message] = []

    if needs and not has_source:
        warnings.append(Message(Advisory.NO_SOURCE_RATE))

    if needs and state.last_irrigation is not None and state.min_interval_h:
        hours = (state.now - state.last_irrigation).total_seconds() / 3600
        if hours < state.min_interval_h:
            warnings.append(
                Message(
                    Advisory.MIN_INTERVAL,
                    {"hours_since": hours, "min_interval_h": state.min_interval_h},
                )
            )

    if (
        needs
        and state.weekly_cap_mm is not None
        and state.irrigation_7d_mm + amount_mm > state.weekly_cap_mm
    ):
        warnings.append(
            Message(
                Advisory.WEEKLY_CAP,
                {
                    "irrigation_7d_mm": state.irrigation_7d_mm,
                    "amount_mm": amount_mm,
                    "weekly_cap_mm": state.weekly_cap_mm,
                },
            )
        )

    sensor = state.soil_sensor
    if sensor is not None:
        if needs and sensor.wet_pct is not None and sensor.value_pct >= sensor.wet_pct:
            warnings.append(
                Message(
                    Advisory.SOIL_SENSOR_WET,
                    {"value_pct": sensor.value_pct, "wet_pct": sensor.wet_pct},
                )
            )
        if (
            not needs
            and sensor.dry_pct is not None
            and sensor.value_pct <= sensor.dry_pct
        ):
            warnings.append(
                Message(
                    Advisory.SOIL_SENSOR_DRY,
                    {"value_pct": sensor.value_pct, "dry_pct": sensor.dry_pct},
                )
            )

    if (
        needs
        and state.forecast_rain_mm is not None
        and state.forecast_rain_mm >= max(state.forecast_threshold_mm, 0.1)
    ):
        warnings.append(
            Message(Advisory.RAIN_FORECAST, {"forecast_mm": state.forecast_rain_mm})
        )

    return warnings
