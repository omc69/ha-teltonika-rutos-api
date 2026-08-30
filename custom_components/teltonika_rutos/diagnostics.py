"""Diagnostics for the Teltonika RutOS integration.

Users attach diagnostics downloads to bug reports without reading them, so
anything that identifies the person, the SIM or the network must be removed
here. The router's raw answers carry IMSI, ICCID, IMEI, WLAN keys, SSIDs, MAC
addresses and the VPN endpoint host.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import SENSITIVE_KEYS
from .coordinator import TeltonikaConfigEntry

REDACT_CONFIG = {CONF_HOST, CONF_USERNAME, CONF_PASSWORD}


def _redact_deep(value: Any) -> Any:
    """Redact sensitive keys at every depth, including inside lists.

    ``async_redact_data`` only walks dicts and lists of dicts; the RutOS
    payloads nest lists of dicts inside dicts, so recurse explicitly.
    """
    if isinstance(value, dict):
        return {
            key: ("**REDACTED**" if key.lower() in SENSITIVE_KEYS else _redact_deep(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_deep(item) for item in value]
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TeltonikaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data

    return {
        "entry": async_redact_data(dict(entry.data), REDACT_CONFIG),
        "options": dict(entry.options),
        "device": _redact_deep(data.device),
        "gps": _redact_deep(data.gps),
        "modems": _redact_deep(data.modems),
        "interfaces": _redact_deep(data.interfaces),
    }
