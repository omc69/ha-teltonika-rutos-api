"""Constants for the Teltonika RutOS integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "teltonika_rutos"
MANUFACTURER: Final = "Teltonika Networks"

CONF_VERIFY_SSL: Final = "verify_ssl"

DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 600

# RutOS hands out a token that is valid for 299 s. Renew well before that so a
# long-running request can never be cut off mid-flight by an expiring token.
TOKEN_RENEW_MARGIN: Final = 60

# --- Endpoints -------------------------------------------------------------
# Verified against RUTC50 / RutOS 7.24.1 / API 1.16.1 on 2026-08-30.
# See docs/rutos-api-map.md for the full survey, including which endpoints
# answer 403/404/501 on this model.

EP_LOGIN: Final = "login"
EP_UNAUTHORIZED: Final = "unauthorized/status"
EP_DEVICE: Final = "system/device/status"
EP_GPS: Final = "gps/position/status"
EP_MODEMS: Final = "modems/status"
EP_INTERFACES: Final = "interfaces/status"
EP_WIREGUARD: Final = "wireguard/config"

# Keys in the coordinator's data dict.
DATA_DEVICE: Final = "device"
DATA_GPS: Final = "gps"
DATA_MODEM: Final = "modem"
DATA_INTERFACES: Final = "interfaces"

# Interfaces that carry no useful traffic counters.
IGNORED_INTERFACES: Final = frozenset({"loopback", "lo"})

# Field names whose values must never leave the instance: personal identifiers
# and secrets. Applied to diagnostics downloads and to debug logging.
SENSITIVE_KEYS: Final = frozenset(
    {
        "imsi",
        "iccid",
        "imei",
        "macaddr",
        "mac",
        "ssid",
        "key",
        "psk",
        "password",
        "private_key",
        "public_key",
        "preshared_key",
        "token",
        "serial",
        "device_identifier",
        "endpoint_host",
        "pincode",
    }
)
