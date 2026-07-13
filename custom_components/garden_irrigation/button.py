"""Button platform for garden_irrigation.

Milestone 9 scope only:
  - `start_cycle` / `end_cycle`: declare a manual cycle active/inactive for
    `select.active_cycle_zone`'s current zone (coordinator.py's
    `async_start_cycle`/`async_end_cycle`). Purely declarative - no side
    effect on the deficit or the irrigation log until the user actually
    records the cycle via the existing `record_irrigation` service/backend
    (irrigation_log.py, unchanged). No prefill of that form's minutes field
    happens anywhere in this integration (CLAUDE.md).
  - `start_calibration` / `finish_calibration` (one pair per zone): an
    explicit override for recommendation.py's automatic WH51 calibration
    marker (Milestone 7 starts the 14-day window at the first observed
    reading; this lets the user force a restart or an early finish instead).

recommendation.py is out of scope to touch in M9, so the override does NOT
call into it directly. Instead it reads/writes the SAME store file and dict
shape recommendation.py's own `_Wh51CalibrationState.to_dict()`/`from_dict()`
already define (`{"first_seen": iso|None, "baseline_min": ..., "baseline_max":
...}`), then calls `RecommendationEngine.async_setup()` again - an already
public, idempotent method whose only effect is reloading that same
calibration baseline from the store into memory - so the running engine
picks up the override immediately, with no migration and no change to
recommendation.py's formulas/thresholds/classification logic.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ZONE1_NAME,
    CONF_ZONE2_NAME,
    DEFAULT_CALIBRATION_DAYS,
    DEFAULT_ZONE1_NAME,
    DEFAULT_ZONE2_NAME,
    DOMAIN,
    STORAGE_KEY_RECOMMENDATION,
    ZONE_1,
    ZONES,
)
from .coordinator import GardenIrrigationCoordinator
from .entity import GardenIrrigationEntity
from .storage import GardenIrrigationStore


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the garden_irrigation button platform."""
    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = [
        StartCycleButton(coordinator, entry),
        EndCycleButton(coordinator, entry),
    ]
    for zone_id in ZONES:
        entities.extend(
            [
                StartCalibrationButton(coordinator, entry, zone_id),
                FinishCalibrationButton(coordinator, entry, zone_id),
            ]
        )
    async_add_entities(entities)


def _zone_name(entry: ConfigEntry, zone_id: str) -> str:
    """Return the user-configured display name for `zone_id`.

    Re-implemented here (not imported from sensor.py/binary_sensor.py -
    private helpers, and both are out of scope to touch in M9).
    """
    if zone_id == ZONE_1:
        return str(entry.data.get(CONF_ZONE1_NAME, DEFAULT_ZONE1_NAME))
    return str(entry.data.get(CONF_ZONE2_NAME, DEFAULT_ZONE2_NAME))


class StartCycleButton(GardenIrrigationEntity, ButtonEntity):
    """Declare a manual cycle active for `select.active_cycle_zone`'s zone."""

    _attr_translation_key = "start_cycle"

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize with a stable unique_id derived from the config entry."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_start_cycle"

    async def async_press(self) -> None:
        """Start the declared cycle - purely declarative, see module docstring."""
        await self.coordinator.async_start_cycle()


class EndCycleButton(GardenIrrigationEntity, ButtonEntity):
    """Clear the declared-active-cycle state."""

    _attr_translation_key = "end_cycle"

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize with a stable unique_id derived from the config entry."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_end_cycle"

    async def async_press(self) -> None:
        """End the declared cycle."""
        await self.coordinator.async_end_cycle()


class _CalibrationOverrideButton(GardenIrrigationEntity, ButtonEntity):
    """Shared base for the per-zone WH51 calibration override buttons."""

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

    async def _async_override_calibration(self, wh51_entry: dict[str, Any]) -> None:
        """Write `wh51_entry` for this zone into recommendation.py's own
        store (same dict shape it already persists), then reload the live
        engine from it - see module docstring for why this avoids touching
        recommendation.py itself."""
        store = GardenIrrigationStore(self.coordinator.hass, STORAGE_KEY_RECOMMENDATION)
        stored = await store.async_load()
        wh51 = dict(stored.get("wh51", {}))
        wh51[self.zone_id] = wh51_entry
        await store.async_save({**stored, "wh51": wh51})
        await self.coordinator.recommendation.async_setup()
        await self.coordinator.async_request_refresh()


class StartCalibrationButton(_CalibrationOverrideButton):
    """Force-restart the 14-day WH51 calibration window for this zone, now.

    Clears any previously observed baseline min/max too: a fresh window
    should not carry over readings from before this explicit restart.
    """

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zone_id: str
    ) -> None:
        """Initialize the per-zone start-calibration button."""
        super().__init__(coordinator, entry, zone_id, "start_calibration")

    async def async_press(self) -> None:
        """Restart calibration for this zone from this instant."""
        await self._async_override_calibration(
            {
                "first_seen": dt_util.now().isoformat(),
                "baseline_min": None,
                "baseline_max": None,
            }
        )


class FinishCalibrationButton(_CalibrationOverrideButton):
    """Force this zone's calibration to be considered complete, now.

    Keeps whatever baseline min/max has already been observed - if none has
    been observed yet, this is a no-op with respect to calibrated status
    (there is nothing to compute a device-relative position against, so no
    number is invented; see recommendation.py's own no-fallback rule).
    """

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry, zone_id: str
    ) -> None:
        """Initialize the per-zone finish-calibration button."""
        super().__init__(coordinator, entry, zone_id, "finish_calibration")

    async def async_press(self) -> None:
        """Declare calibration finished for this zone using data observed so far.

        Reads the existing baseline from the LIVE in-memory calibration state
        (`coordinator.recommendation`), not from disk: recommendation.py
        debounces its own saves by a few seconds, so a fresh-off-disk read
        here could miss the most recent observation.
        """
        existing = self.coordinator.recommendation._calibration[self.zone_id]
        forced_first_seen = dt_util.now() - timedelta(
            days=DEFAULT_CALIBRATION_DAYS, hours=1
        )
        await self._async_override_calibration(
            {
                "first_seen": forced_first_seen.isoformat(),
                "baseline_min": existing.baseline_min,
                "baseline_max": existing.baseline_max,
            }
        )
