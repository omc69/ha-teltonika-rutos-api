"""The Teltonika RutOS integration."""

from __future__ import annotations

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RutosClient
from .const import CONF_VERIFY_SSL, DEFAULT_SCAN_INTERVAL
from .coordinator import TeltonikaConfigEntry, TeltonikaCoordinator

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
