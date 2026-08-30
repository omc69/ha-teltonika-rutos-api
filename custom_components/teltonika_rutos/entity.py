"""Shared entity base for the Teltonika RutOS integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_ID, CONF_MODEL, DOMAIN, MANUFACTURER
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
        # Fall back to the entry id only for entries created before the
        # device identifier was stored; async_migrate_entry backfills it.
        device_id = entry.data.get(CONF_DEVICE_ID) or entry.entry_id
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=MANUFACTURER,
            name=entry.title,
            model=entry.data.get(CONF_MODEL),
            configuration_url=coordinator.client.base_url,
        )

    @property
    def _board(self) -> dict[str, Any]:
        """Return the board section of the device description."""
        board = self.coordinator.data.device.get("board")
        return board if isinstance(board, dict) else {}
