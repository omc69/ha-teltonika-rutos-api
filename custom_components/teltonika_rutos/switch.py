"""Switch platform for the Teltonika RutOS integration.

Currently one switch per WireGuard instance. The switch reads its state from
the router on every cycle, so it also follows changes made in the router's own
web interface or by anything else.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import RutosError, to_bool
from .const import DOMAIN
from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator
from .entity import TeltonikaEntity

_LOGGER = logging.getLogger(__name__)

# A peer routing these takes the whole default route through the tunnel.
FULL_TUNNEL_ROUTES = frozenset({"0.0.0.0/0", "::/0"})


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeltonikaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one switch per configured WireGuard instance."""
    coordinator = entry.runtime_data
    async_add_entities(
        WireGuardSwitch(coordinator, entry, instance_id)
        for instance_id in coordinator.data.wireguard
    )


class WireGuardSwitch(TeltonikaEntity, SwitchEntity):
    """Enables or disables one WireGuard instance."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:vpn"

    def __init__(
        self,
        coordinator: TeltonikaCoordinator,
        entry: TeltonikaConfigEntry,
        instance_id: str,
    ) -> None:
        """Initialise the switch."""
        super().__init__(coordinator, entry, f"wireguard_{instance_id}")
        self._instance_id = instance_id
        self._attr_name = f"WireGuard {instance_id}"

    @property
    def _instance(self) -> dict[str, Any] | None:
        """Return this instance from the latest snapshot."""
        return self.coordinator.data.wireguard.get(self._instance_id)

    @property
    def is_on(self) -> bool | None:
        """Return whether the tunnel is enabled, straight from the router."""
        instance = self._instance
        return None if instance is None else to_bool(instance.get("enabled"))

    @property
    def available(self) -> bool:
        """Report unavailable while the instance is missing from the snapshot."""
        return super().available and self.is_on is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose addresses, port and the routing scope of the peers.

        ``full_tunnel`` is the one worth surfacing: with it, enabling the
        switch sends *all* traffic through the tunnel, not just the remote
        subnet. A dashboard can warn on that; the integration does not refuse
        it — that is the user's decision.
        """
        instance = self._instance or {}
        peers = self.coordinator.wireguard_peers.get(self._instance_id, [])

        allowed: set[str] = set()
        descriptions: list[str] = []
        for peer in peers:
            allowed.update(peer.get("allowed_ips") or [])
            if description := peer.get("description"):
                descriptions.append(description)

        return {
            "instance": self._instance_id,
            "addresses": instance.get("addresses"),
            "listen_port": instance.get("listen_port"),
            "peers": descriptions or None,
            "allowed_ips": sorted(allowed) or None,
            "full_tunnel": bool(allowed & FULL_TUNNEL_ROUTES),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the tunnel."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the tunnel."""
        await self._async_set(False)

    async def _async_set(self, enabled: bool) -> None:
        """Write the new state and read it back.

        The PUT applies immediately on RutOS — no separate commit. Refreshing
        afterwards means the entity shows what the router actually did rather
        than what was asked for.
        """
        try:
            await self.coordinator.client.async_set_wireguard_enabled(
                self._instance_id, enabled
            )
        except RutosError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="wireguard_switch_failed",
                translation_placeholders={
                    "instance": self._instance_id,
                    "error": str(err),
                },
            ) from err

        # Enabling a full tunnel reroutes the router's own traffic, which can
        # briefly interrupt this very connection. Let the next scheduled cycle
        # settle it rather than failing the call on a refresh timeout.
        try:
            await self.coordinator.async_request_refresh()
        except Exception:  # noqa: BLE001 - refresh is best effort here
            _LOGGER.debug(
                "Refresh after switching %s did not complete; "
                "the next cycle will pick up the state",
                self._instance_id,
            )
