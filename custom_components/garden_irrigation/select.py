"""Select platform for garden_irrigation.

Milestone 9 scope only:
  - `select.mode`: the operational mode, `calibration` or `monitoring` only
    (CLAUDE.md: no `automation` mode, not even as a placeholder). This is
    purely a UX/status indicator - changing it never alters balance,
    recommendation, or the irrigation log retroactively (or at all).
  - `select.active_cycle_zone`: which zone the declared-cycle buttons
    (button.py) target next. Also purely declarative/UX; it does not itself
    start or stop anything.

Both read/write through `coordinator.mode`/`coordinator.selected_cycle_zone`
(persisted by coordinator.py's own operational-state store) rather than
holding any state locally, so every entity always reflects the same shared
truth.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODES, ZONES
from .coordinator import GardenIrrigationCoordinator
from .entity import GardenIrrigationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the garden_irrigation select platform."""
    coordinator: GardenIrrigationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ModeSelect(coordinator, entry),
            ActiveCycleZoneSelect(coordinator, entry),
        ]
    )


class ModeSelect(GardenIrrigationEntity, SelectEntity):
    """The operational mode: `calibration` or `monitoring` only.

    v1 exposes exactly these two options - never `automation`, matching
    const.py's MODES list (CLAUDE.md golden rule).
    """

    _attr_options = MODES
    _attr_translation_key = "mode"

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize with a stable unique_id derived from the config entry."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_mode"

    @property
    def current_option(self) -> str:
        """Always reflects `coordinator.mode` - no locally cached value."""
        return self.coordinator.mode

    async def async_select_option(self, option: str) -> None:
        """Persist the new mode; never alters balance/recommendation/log data."""
        await self.coordinator.async_set_mode(option)


class ActiveCycleZoneSelect(GardenIrrigationEntity, SelectEntity):
    """Which zone `button.start_cycle` will declare active next."""

    _attr_options = ZONES
    _attr_translation_key = "active_cycle_zone"

    def __init__(
        self, coordinator: GardenIrrigationCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize with a stable unique_id derived from the config entry."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_active_cycle_zone"

    @property
    def current_option(self) -> str:
        """Always reflects `coordinator.selected_cycle_zone`."""
        return self.coordinator.selected_cycle_zone

    async def async_select_option(self, option: str) -> None:
        """Persist which zone a subsequent `start_cycle` press will target."""
        await self.coordinator.async_set_selected_cycle_zone(option)
