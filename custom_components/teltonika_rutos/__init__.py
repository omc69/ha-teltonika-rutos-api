"""The Teltonika RutOS integration."""

from __future__ import annotations

import logging

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RutosClient
from .const import CONF_DEVICE_ID, CONF_VERIFY_SSL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: TeltonikaConfigEntry) -> bool:
    """Set up one router from a config entry."""
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, False)
    client = RutosClient(
        async_get_clientsession(hass, verify_ssl=verify_ssl),
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        verify_ssl=verify_ssl,
    )

    coordinator = TeltonikaCoordinator(
        hass,
        entry,
        client,
        entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TeltonikaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: TeltonikaConfigEntry) -> bool:
    """Migrate an old config entry.

    Version 1 built every unique_id from the config entry id. That id is
    regenerated whenever the integration is removed and added again, so all
    entities were orphaned and recreated under new entity_ids — silently
    breaking dashboards, automations and history.

    Version 2 uses the device identifier from ``unauthorized/status``, which
    stays the same for the life of the router. The identifier is already
    stored as the entry's unique_id, so the migration needs no network access.
    """
    if entry.version > 2:
        # Downgrade is not supported; refuse rather than corrupt the registry.
        return False

    if entry.version == 1:
        device_id = entry.unique_id
        if not device_id:
            # An entry created before the unique_id was set. Keep the entry id
            # as the identifier so nothing is renamed, and record it so future
            # versions have something stable to work with.
            device_id = entry.entry_id
            _LOGGER.warning(
                "Config entry has no device identifier; keeping the entry id. "
                "Remove and re-add the integration to pick up the router's own "
                "identifier"
            )

        old_prefix = f"{entry.entry_id}_"
        new_prefix = f"{device_id}_"

        if old_prefix != new_prefix:

            @callback
            def _migrate_unique_id(
                registry_entry: er.RegistryEntry,
            ) -> dict[str, str] | None:
                """Rewrite one entity's unique_id, keeping its entity_id."""
                if registry_entry.unique_id.startswith(old_prefix):
                    return {
                        "new_unique_id": new_prefix
                        + registry_entry.unique_id[len(old_prefix) :]
                    }
                return None

            await er.async_migrate_entries(hass, entry.entry_id, _migrate_unique_id)

            # The device carries the old identifier too; without this the next
            # setup would create a second device and leave the entities behind
            # on the old one.
            device_registry = dr.async_get(hass)
            if device := device_registry.async_get_device(
                identifiers={(DOMAIN, entry.entry_id)}
            ):
                device_registry.async_update_device(
                    device.id, new_identifiers={(DOMAIN, device_id)}
                )

        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_DEVICE_ID: device_id},
            version=2,
        )
        _LOGGER.info(
            "Migrated to version 2: unique_ids now follow the device identifier"
        )

    return True
