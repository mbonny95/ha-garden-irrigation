"""Sensor platform for garden_irrigation.

Milestone 1 added the single diagnostic `data_quality` sensor. Milestone 5
completes the platform with the computed decision-support sensors backed by
data already produced by weather.py/et0.py/balance.py: daily ET0, and the
per-zone ETc, deficit, TAW, RAW, and effective rain. `irrigation_7d` reads
irrigation_log.py's event log directly (see Irrigation7dZoneSensor's
docstring) now that the `record_irrigation` action exists, instead of
balance.py's own 7-day figure. Sensors that the approved plan's section 3.1
lists but that depend on the recommendation engine (recommended mm/minutes,
estimated liters, last_recommendation) or on period-aggregated counters
(irrigation today/week/month/season, liters totals) are still NOT added here
- there is no data source for them yet.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfPrecipitationDepth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .balance import ZoneBalanceResult
from .const import (
    CONF_ZONE1_NAME,
    CONF_ZONE2_NAME,
    DATA_QUALITY_INITIALIZING,
    DATA_QUALITY_NOT_CONFIGURED,
    DATA_QUALITY_STATES,
    DEFAULT_AWC_MM_PER_M,
    DEFAULT_KC,
    DEFAULT_P_DEPLETION_FRACTION,
    DEFAULT_RAIN_EFFECTIVE_FACTOR,
    DEFAULT_ROOT_DEPTH_MM,
    DEFAULT_WEEKLY_CAP_MM,
    DEFAULT_ZONE1_NAME,
    DEFAULT_ZONE2_NAME,
    DOMAIN,
    SOURCES,
    ZONE_1,
    ZONES,
)
from .coordinator import GardenIrrigationCoordinator
from .entity import GardenIrrigationEntity
from .et0 import ET0Result
from .irrigation_log import IrrigationAggregate


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the garden_irrigation sensor platform."""
    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        DataQualitySensor(coordinator, entry),
        Et0DailySensor(coordinator, entry),
    ]
    for zone_id in ZONES:
        entities.extend(
            [
                EtcZoneSensor(coordinator, entry, zone_id),
                DeficitZoneSensor(coordinator, entry, zone_id),
                TawZoneSensor(coordinator, entry, zone_id),
                RawZoneSensor(coordinator, entry, zone_id),
                EffectiveRainZoneSensor(coordinator, entry, zone_id),
                Irrigation7dZoneSensor(coordinator, entry, zone_id),
            ]
        )
    async_add_entities(entities)


def _zone_name(entry: ConfigEntry, zone_id: str) -> str:
    """Return the user-configured display name for `zone_id`."""
    if zone_id == ZONE_1:
        return str(entry.data.get(CONF_ZONE1_NAME, DEFAULT_ZONE1_NAME))
    return str(entry.data.get(CONF_ZONE2_NAME, DEFAULT_ZONE2_NAME))


class DataQualitySensor(GardenIrrigationEntity, SensorEntity):
    """Diagnostic sensor reporting overall data-quality status.

    Milestone 1: always available, and its value is one of exactly two
    states — `not_configured` before the coordinator has completed its first
    refresh, `initializing` afterwards. Real stale/battery/signal/weather
    quality logic is added in Milestone 2 without changing this contract.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = DATA_QUALITY_STATES
    _attr_translation_key = "data_quality"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize with a stable unique_id derived from the config entry."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_data_quality"

    @property
    def available(self) -> bool:
        """Always available in Milestone 1 (never unavailable)."""
        return True

    @property
    def native_value(self) -> str:
        """Return `not_configured` pre-refresh, `initializing` afterwards."""
        data = self.coordinator.data
        if not data:
            return DATA_QUALITY_NOT_CONFIGURED
        return str(data.get("data_quality", DATA_QUALITY_INITIALIZING))


class Et0DailySensor(GardenIrrigationEntity, SensorEntity):
    """Daily FAO-56 reference evapotranspiration for the current in-progress day.

    Availability follows the coordinator's own update success (standard
    CoordinatorEntity behavior): a failed coordinator update makes this
    unavailable, but a successful update with incomplete weather inputs
    reports `unknown` (native_value None) per CLAUDE.md - there is no
    automatic fallback, so an incomplete ET0 is never guessed.
    """

    _attr_translation_key = "et0_daily"
    _attr_native_unit_of_measurement = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize with a stable unique_id derived from the config entry."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_et0_daily"

    def _et0_result(self) -> ET0Result | None:
        data = self.coordinator.data
        if not data:
            return None
        result: ET0Result | None = data.get("et0")
        return result

    @property
    def native_value(self) -> float | None:
        """The computed ET0 in mm, or None (unknown) if incomplete/not yet run."""
        result = self._et0_result()
        return result.et0_mm if result is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Intermediate FAO-56 terms, for diagnosis (see et0.py ET0Result)."""
        result = self._et0_result()
        if result is None:
            return None
        return {
            "method": "fao56",
            "day": result.day.isoformat(),
            "rs_mj": result.rs_mj,
            "rn_mj": result.rn_mj,
            "u2_ms": result.u2_ms,
            "es_kpa": result.es_kpa,
            "ea_kpa": result.ea_kpa,
            "incomplete": result.incomplete,
            "missing_inputs": list(result.missing_inputs),
        }


class _ZoneBalanceSensor(GardenIrrigationEntity, SensorEntity):
    """Shared base for the per-zone sensors backed by `coordinator.data["balance"]`.

    All of these report the most recently completed local day's balance
    result for their zone (see balance.py) - `day`/`applied`/`skipped_reason`
    are exposed on every one of them so it's always clear whether the value
    reflects a freshly applied day, an already-processed one, or a day still
    pending finalized weather data.
    """

    _attr_native_unit_of_measurement = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: GardenIrrigationCoordinator,
        entry: ConfigEntry,
        zone_id: str,
        key: str,
    ) -> None:
        """Initialize with a per-zone unique_id and translation placeholder."""
        super().__init__(coordinator, entry)
        self.zone_id = zone_id
        self._attr_unique_id = f"{entry.entry_id}_{key}_{zone_id}"
        self._attr_translation_key = key
        self._attr_translation_placeholders = {"zone_name": _zone_name(entry, zone_id)}

    def _balance_result(self) -> ZoneBalanceResult | None:
        data = self.coordinator.data
        if not data:
            return None
        balance: dict[str, ZoneBalanceResult] = data.get("balance", {})
        return balance.get(self.zone_id)

    def _extra_attributes(self, result: ZoneBalanceResult) -> dict[str, Any]:
        """Subclasses add their own attributes on top of the common ones."""
        return {}

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Common day/applied/skipped_reason plus subclass-specific attributes."""
        result = self._balance_result()
        if result is None:
            return None
        return {
            "day": result.day.isoformat(),
            "applied": result.applied,
            "skipped_reason": result.skipped_reason,
            **self._extra_attributes(result),
        }


class EtcZoneSensor(_ZoneBalanceSensor):
    """Crop evapotranspiration (ETc = ET0 * Kc) for the zone's last processed day."""

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zone_id: str
    ) -> None:
        """Initialize the per-zone ETc sensor."""
        super().__init__(coordinator, entry, zone_id, "etc")

    @property
    def native_value(self) -> float | None:
        """ETc in mm, or None until a day has actually been applied."""
        result = self._balance_result()
        return result.etc_mm if result is not None else None

    def _extra_attributes(self, result: ZoneBalanceResult) -> dict[str, Any]:
        et0_mm = result.etc_mm / DEFAULT_KC if result.etc_mm is not None else None
        return {"kc": DEFAULT_KC, "et0_mm": et0_mm}


class DeficitZoneSensor(_ZoneBalanceSensor):
    """Current water deficit for the zone (persists across days, clamped [0, TAW])."""

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zone_id: str
    ) -> None:
        """Initialize the per-zone deficit sensor."""
        super().__init__(coordinator, entry, zone_id, "deficit")

    @property
    def native_value(self) -> float | None:
        """Current deficit in mm."""
        result = self._balance_result()
        return result.deficit_mm if result is not None else None

    def _extra_attributes(self, result: ZoneBalanceResult) -> dict[str, Any]:
        return {
            "taw_mm": result.taw_mm,
            "raw_mm": result.raw_mm,
            "p": DEFAULT_P_DEPLETION_FRACTION,
        }


class TawZoneSensor(_ZoneBalanceSensor):
    """Total Available Water for the zone: (root_depth/1000) * AWC."""

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zone_id: str
    ) -> None:
        """Initialize the per-zone TAW sensor."""
        super().__init__(coordinator, entry, zone_id, "taw")

    @property
    def native_value(self) -> float | None:
        """TAW in mm."""
        result = self._balance_result()
        return result.taw_mm if result is not None else None

    def _extra_attributes(self, result: ZoneBalanceResult) -> dict[str, Any]:
        return {
            "root_depth_mm": DEFAULT_ROOT_DEPTH_MM,
            "awc_mm_per_m": DEFAULT_AWC_MM_PER_M,
        }


class RawZoneSensor(_ZoneBalanceSensor):
    """Readily Available Water for the zone: TAW * p."""

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zone_id: str
    ) -> None:
        """Initialize the per-zone RAW sensor."""
        super().__init__(coordinator, entry, zone_id, "raw")

    @property
    def native_value(self) -> float | None:
        """RAW in mm."""
        result = self._balance_result()
        return result.raw_mm if result is not None else None

    def _extra_attributes(self, result: ZoneBalanceResult) -> dict[str, Any]:
        return {"taw_mm": result.taw_mm, "p": DEFAULT_P_DEPLETION_FRACTION}


class EffectiveRainZoneSensor(_ZoneBalanceSensor):
    """Effective rain applied to the zone's balance for its last processed day."""

    _attr_device_class = SensorDeviceClass.PRECIPITATION

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zone_id: str
    ) -> None:
        """Initialize the per-zone effective-rain sensor."""
        super().__init__(coordinator, entry, zone_id, "effective_rain")

    @property
    def native_value(self) -> float | None:
        """Effective rain in mm, or None until a day has actually been applied."""
        result = self._balance_result()
        return result.eff_rain_mm if result is not None else None

    def _extra_attributes(self, result: ZoneBalanceResult) -> dict[str, Any]:
        finalized_day = self.coordinator.weather.get_finalized_day(result.day)
        return {
            "factor": DEFAULT_RAIN_EFFECTIVE_FACTOR,
            "daily_rain_raw_mm": (
                finalized_day.rain_mm if finalized_day is not None else None
            ),
        }


class Irrigation7dZoneSensor(GardenIrrigationEntity, SensorEntity):
    """User-recorded irrigation over the trailing sliding 7x24h window.

    Reads irrigation_log.py's event log directly
    (`coordinator.irrigation_log.aggregate(..., since=, until=)`) instead of
    `coordinator.data["balance"][zone_id].irrigation_7d_mm`. Two reasons:

    - balance.py's own figure is anchored to the end of the last *finalized*
      day ("yesterday"), not to now - anything recorded today is invisible
      to it until the next 05:30 rollover (see balance.py's
      `_unchanged_result`/`pending_result`). Recomputing the window here
      with `dt_util.now()` on every read means a cycle recorded seconds ago
      is reflected immediately.
    - balance.py only tracks a per-zone total, never a per-source split;
      irrigation_log.py's event log already carries `source` per event, so
      the breakdown below is a direct read, not a new computation.

    Governs the weekly cap on its own (never on effective rain - see
    CLAUDE.md). Uncalibrated-source events are excluded from mm here too
    (IrrigationAggregate.mm only sums calibrated events - see
    IrrigationLog.aggregate).
    """

    _attr_native_unit_of_measurement = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zone_id: str
    ) -> None:
        """Initialize the per-zone 7-day irrigation sensor."""
        super().__init__(coordinator, entry)
        self.zone_id = zone_id
        self._attr_unique_id = f"{entry.entry_id}_irrigation_7d_{zone_id}"
        self._attr_translation_key = "irrigation_7d"
        self._attr_translation_placeholders = {"zone_name": _zone_name(entry, zone_id)}

    def _breakdown(self) -> dict[str, IrrigationAggregate]:
        """Per-source aggregate over the trailing 7x24h window, as of now."""
        until = dt_util.now()
        since = until - timedelta(days=7)
        return {
            source: self.coordinator.irrigation_log.aggregate(
                self.zone_id, source=source, since=since, until=until
            )
            for source in SOURCES
        }

    def _cap_mm(self) -> float:
        """The configured weekly cap, from the last balance result if known.

        Falls back to the const.py default before the first coordinator
        refresh - the cap is a static config value, not something that
        depends on balance.py's own (potentially stale) irrigation figure.
        """
        data = self.coordinator.data
        balance: dict[str, ZoneBalanceResult] = (data or {}).get("balance", {})
        result = balance.get(self.zone_id)
        return result.weekly_cap_mm if result is not None else DEFAULT_WEEKLY_CAP_MM

    @property
    def native_value(self) -> float:
        """Recorded irrigation in mm over the trailing 7 days, all sources summed."""
        return sum(aggregate.mm for aggregate in self._breakdown().values())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Per-source breakdown plus the weekly cap context."""
        breakdown = self._breakdown()
        total_mm = sum(aggregate.mm for aggregate in breakdown.values())
        cap_mm = self._cap_mm()
        return {
            "breakdown": {
                source: {
                    "mm": aggregate.mm,
                    "liters": aggregate.liters,
                    "count": aggregate.count,
                }
                for source, aggregate in breakdown.items()
            },
            "cap_mm": cap_mm,
            "remaining_mm": max(cap_mm - total_mm, 0.0),
            "weekly_cap_reached": total_mm >= cap_mm,
        }
