"""Client for the Teltonika RutOS REST API.

Every RutOS quirk is contained in this module so the rest of the integration
can work with ordinary Python types:

* Values arrive as strings — even numbers and booleans (``"0"``, ``"49.1557"``).
  They are converted here; no platform file ever sees a numeric string.
* The session token expires after 299 seconds and is renewed proactively.
* The router presents a self-signed certificate, so TLS verification is off by
  default (see ``verify_ssl``).
* Several endpoints answer 403 or 501 depending on model and account rights.
  Those raise dedicated exceptions instead of failing the whole update.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp
from yarl import URL

from .const import (
    EP_DEVICE,
    EP_GPS,
    EP_INTERFACES,
    EP_LOGIN,
    EP_MODEMS,
    EP_UNAUTHORIZED,
    EP_WIREGUARD,
    TOKEN_RENEW_MARGIN,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)


class RutosError(Exception):
    """Base class for every error raised by this client."""


class RutosConnectionError(RutosError):
    """The router could not be reached."""


class RutosAuthError(RutosError):
    """Credentials were rejected."""


class RutosPermissionError(RutosError):
    """The account is not allowed to use this endpoint (HTTP 403).

    Observed on RUTC50 for ``system/fw/status`` and ``backup/config`` even
    though the account reports ``group: admin``.
    """


class RutosNotSupportedError(RutosError):
    """The endpoint does not exist on this model or firmware (404 / 501)."""


def to_float(value: Any) -> float | None:
    """Convert a RutOS value to float, or None if it is not a number."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    """Convert a RutOS value to int, or None if it is not a number.

    Floats arriving as ``"10.0"`` are accepted and truncated.
    """
    number = to_float(value)
    return None if number is None else int(number)


def to_bool(value: Any) -> bool | None:
    """Convert a RutOS flag to bool.

    RutOS uses ``"0"``/``"1"`` strings, but some endpoints return real
    booleans. Both are handled; anything else yields None.
    """
    if isinstance(value, bool):
        return value
    if value in ("1", 1):
        return True
    if value in ("0", 0):
        return False
    return None


class RutosClient:
    """Talks to one RutOS device."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
        *,
        verify_ssl: bool = False,
    ) -> None:
        """Initialise the client. ``host`` may be a bare IP or a full URL."""
        self._session = session
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._base = self._build_base_url(host)
        self._token: str | None = None
        self._token_expires: float = 0.0
        self._login_lock = asyncio.Lock()

    @staticmethod
    def _build_base_url(host: str) -> URL:
        """Accept ``192.168.1.1``, ``https://host`` or ``https://host/api``."""
        raw = host.strip().rstrip("/")
        if raw.endswith("/api"):
            raw = raw[: -len("/api")]
        if "://" not in raw:
            raw = f"https://{raw}"
        return URL(raw)

    @property
    def base_url(self) -> str:
        """Return the router's base URL as a string."""
        return str(self._base)

    # --- plumbing ---------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> Any:
        """Perform one request and unwrap the RutOS envelope."""
        headers: dict[str, str] = {}
        if authenticated:
            headers["Authorization"] = f"Bearer {await self._async_token()}"

        url = self._base / "api" / path.lstrip("/")
        try:
            async with self._session.request(
                method,
                url,
                json=json_body,
                headers=headers,
                ssl=self._verify_ssl,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                status = response.status
                # RutOS answers errors as JSON too, so read the body first and
                # only then decide — the payload often names the actual cause.
                try:
                    payload = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    payload = None

        except asyncio.TimeoutError as err:
            raise RutosConnectionError(f"Timeout talking to {url}") from err
        except aiohttp.ClientError as err:
            raise RutosConnectionError(f"Cannot reach {url}: {err}") from err

        if status == 401:
            # Force a fresh login on the next call.
            self._token = None
            raise RutosAuthError("Router rejected the session token")
        if status == 403:
            raise RutosPermissionError(f"Account may not access {path}")
        if status in (404, 501):
            raise RutosNotSupportedError(f"{path} is not available on this device")
        if status >= 400 or not isinstance(payload, dict):
            raise RutosError(f"{method} {path} failed with HTTP {status}")

        if not payload.get("success", False):
            errors = payload.get("errors") or []
            detail = errors[0].get("error") if errors and isinstance(errors[0], dict) else ""
            raise RutosError(f"{path} reported failure: {detail or 'unknown error'}")

        return payload.get("data")

    async def _async_token(self) -> str:
        """Return a valid token, logging in if needed."""
        async with self._login_lock:
            if self._token and time.monotonic() < self._token_expires:
                return self._token
            return await self._async_login()

    async def _async_login(self) -> str:
        """Log in and remember the token. Caller must hold ``_login_lock``."""
        url = self._base / "api" / EP_LOGIN
        try:
            async with self._session.post(
                url,
                json={"username": self._username, "password": self._password},
                ssl=self._verify_ssl,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                status = response.status
                try:
                    payload = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    payload = None
        except asyncio.TimeoutError as err:
            raise RutosConnectionError(f"Timeout logging in at {url}") from err
        except aiohttp.ClientError as err:
            raise RutosConnectionError(f"Cannot reach {url}: {err}") from err

        if status in (401, 403):
            raise RutosAuthError("Username or password rejected")
        if not isinstance(payload, dict) or not payload.get("success"):
            raise RutosAuthError(f"Login failed with HTTP {status}")

        data = payload.get("data") or {}
        token = data.get("token")
        if not token:
            raise RutosAuthError("Login succeeded but returned no token")

        # Renew well before the router's own expiry so an in-flight request is
        # never cut short. RutOS reports 299 s; the margin makes it ~239 s.
        expires = to_int(data.get("expires")) or 299
        self._token = token
        self._token_expires = time.monotonic() + max(expires - TOKEN_RENEW_MARGIN, 30)
        _LOGGER.debug(
            "Logged in to %s as %s (group %s), token valid %ss",
            self._base.host,
            data.get("username"),
            data.get("group"),
            expires,
        )
        return token

    async def _get(self, path: str) -> Any:
        """GET with one automatic retry after a token rejection."""
        try:
            return await self._request("GET", path)
        except RutosAuthError:
            # The token was refused mid-flight; a single retry with a fresh one
            # covers the race. A second failure is a real credential problem.
            return await self._request("GET", path)

    async def _put(self, path: str, data: dict[str, Any]) -> Any:
        """PUT with one automatic retry after a token rejection."""
        body = {"data": data}
        try:
            return await self._request("PUT", path, json_body=body)
        except RutosAuthError:
            return await self._request("PUT", path, json_body=body)

    # --- public API -------------------------------------------------------

    async def async_probe(self) -> dict[str, Any]:
        """Identify the device without credentials.

        Used by the config flow to tell "wrong address" apart from "wrong
        password" before any login attempt is made.
        """
        data = await self._request("GET", EP_UNAUTHORIZED, authenticated=False)
        return data if isinstance(data, dict) else {}

    async def async_verify_credentials(self) -> dict[str, Any]:
        """Log in once and return the account info."""
        async with self._login_lock:
            await self._async_login()
        return await self.async_probe()

    async def async_get_device(self) -> dict[str, Any]:
        """Return ``system/device/status``."""
        data = await self._get(EP_DEVICE)
        return data if isinstance(data, dict) else {}

    async def async_get_gps(self) -> dict[str, Any]:
        """Return ``gps/position/status``.

        One call carries position, altitude, speed, accuracy, satellites, fix
        status and heading — all sampled at the same moment, unlike the Modbus
        register set where each value is read separately.
        """
        data = await self._get(EP_GPS)
        return data if isinstance(data, dict) else {}

    async def async_get_modems(self) -> list[dict[str, Any]]:
        """Return ``modems/status`` as a list."""
        data = await self._get(EP_MODEMS)
        return data if isinstance(data, list) else []

    async def async_get_interfaces(self) -> list[dict[str, Any]]:
        """Return ``interfaces/status`` as a list."""
        data = await self._get(EP_INTERFACES)
        return data if isinstance(data, list) else []

    async def async_get_wireguard(self) -> list[dict[str, Any]]:
        """Return the configured WireGuard instances."""
        data = await self._get(EP_WIREGUARD)
        return data if isinstance(data, list) else []

    async def async_get_wireguard_peers(self, instance_id: str) -> list[dict[str, Any]]:
        """Return the peers of one WireGuard instance.

        Peers change rarely, so this is fetched once at setup rather than per
        cycle. It is what tells a full tunnel (``allowed_ips`` contains
        ``0.0.0.0/0``) from a split tunnel.
        """
        data = await self._get(f"wireguard/{instance_id}/peers/config")
        return data if isinstance(data, list) else []

    async def async_set_wireguard_enabled(self, instance_id: str, enabled: bool) -> None:
        """Enable or disable one WireGuard instance.

        The PUT applies immediately — RutOS needs no separate commit or apply
        call. Verified on the device: ``uci`` flips, the interface appears or
        disappears and the default route follows.
        """
        await self._put(
            f"{EP_WIREGUARD}/{instance_id}", {"enabled": "1" if enabled else "0"}
        )
