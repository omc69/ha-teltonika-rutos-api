"""Shared entity base for the Teltonika RutOS integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator


class TeltonikaEntity(CoordinatorEntity[TeltonikaCoordinator]):
    """Base class carrying the shared device registry entry."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TeltonikaCoordinator, entry: TeltonikaConfigEntry, key: str
    ) -> None:
        """Initialise the entity and attach it to the router device."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=entry.title,
            model=entry.data.get("model"),
            configuration_url=coordinator.client.base_url,
        )

    @property
    def _board(self) -> dict[str, Any]:
        """Return the board section of the device description."""
        board = self.coordinator.data.device.get("board")
        return board if isinstance(board, dict) else {}
