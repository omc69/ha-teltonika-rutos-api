"""Polling coordinator for the Teltonika RutOS integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    RutosAuthError,
    RutosClient,
    RutosConnectionError,
    RutosError,
    RutosNotSupportedError,
    RutosPermissionError,
)
from .const import DOMAIN, IGNORED_INTERFACES

_LOGGER = logging.getLogger(__name__)

type TeltonikaConfigEntry = ConfigEntry[TeltonikaCoordinator]


@dataclass(slots=True)
class RutosData:
    """One snapshot of the router."""

    device: dict[str, Any] = field(default_factory=dict)
    gps: dict[str, Any] = field(default_factory=dict)
    modems: list[dict[str, Any]] = field(default_factory=list)
    interfaces: dict[str, dict[str, Any]] = field(default_factory=dict)
    wireguard: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def modem(self) -> dict[str, Any] | None:
        """Return the first modem, which is the internal one on RUT devices."""
        return self.modems[0] if self.modems else None


class TeltonikaCoordinator(DataUpdateCoordinator[RutosData]):
    """Fetches everything the entities need in one cycle.

    Four calls per cycle: GPS, modems, interfaces and WireGuard. The static
    device description and the WireGuard peers are read once at setup.
    ``wireless/interfaces/status`` is deliberately left out — it
    is roughly 12 kB because it lists every connected client with its data
    rates, which is far too much to pull every 30 seconds off a small router.
    """

    config_entry: TeltonikaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TeltonikaConfigEntry,
        client: RutosClient,
        scan_interval: int,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.device_info_raw: dict[str, Any] = {}
        # Peers change rarely; read once at setup so the cycle stays at
        # four calls. Keyed by WireGuard instance id.
        self.wireguard_peers: dict[str, list[dict[str, Any]]] = {}
        # Endpoints that answered 404/501 once. They will not come back on the
        # same firmware, so stop asking instead of logging an error per cycle.
        self._unsupported: set[str] = set()

    async def _async_setup(self) -> None:
        """Fetch the static device description once, before the first poll."""
        try:
            self.device_info_raw = await self.client.async_get_device()
        except RutosAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (RutosPermissionError, RutosNotSupportedError) as err:
            # Not fatal — only the model/firmware labels are missing.
            _LOGGER.debug("Device description unavailable: %s", err)
        except RutosError as err:
            raise UpdateFailed(f"Cannot read device description: {err}") from err

        try:
            for instance in await self.client.async_get_wireguard():
                instance_id = instance.get("id")
                if instance_id:
                    self.wireguard_peers[instance_id] = (
                        await self.client.async_get_wireguard_peers(instance_id)
                    )
        except RutosError as err:
            _LOGGER.debug("Cannot read WireGuard peers: %s", err)

    async def _async_update_data(self) -> RutosData:
        """Fetch one snapshot.

        A single endpoint refusing (403) or missing (404/501) must not fail the
        whole update — the remaining entities stay usable. Only an
        authentication failure or an unreachable router aborts the cycle.
        """
        data = RutosData(device=self.device_info_raw)

        try:
            data.gps = await self._fetch("gps", self.client.async_get_gps, {})
            data.modems = await self._fetch("modems", self.client.async_get_modems, [])
            interfaces = await self._fetch(
                "interfaces", self.client.async_get_interfaces, []
            )
            wireguard = await self._fetch(
                "wireguard", self.client.async_get_wireguard, []
            )
        except RutosAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except RutosConnectionError as err:
            raise UpdateFailed(str(err)) from err

        data.interfaces = {
            iface["id"]: iface
            for iface in interfaces
            if isinstance(iface, dict)
            and iface.get("id")
            and iface.get("type") not in IGNORED_INTERFACES
        }
        data.wireguard = {
            instance["id"]: instance
            for instance in wireguard
            if isinstance(instance, dict) and instance.get("id")
        }
        return data

    async def _fetch(self, key: str, call, fallback):
        """Run one endpoint call, tolerating 403/404/501."""
        if key in self._unsupported:
            return fallback
        try:
            return await call()
        except RutosNotSupportedError as err:
            _LOGGER.info("Endpoint %s not available on this device: %s", key, err)
            self._unsupported.add(key)
        except RutosPermissionError as err:
            _LOGGER.warning(
                "Account is not allowed to read %s: %s. "
                "The related entities stay unavailable.",
                key,
                err,
            )
            self._unsupported.add(key)
        except RutosError as err:
            # A transient failure of one endpoint — keep the cycle alive and
            # let the next one try again.
            _LOGGER.debug("Reading %s failed this cycle: %s", key, err)
        return fallback
