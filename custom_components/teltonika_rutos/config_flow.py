"""Config flow for the Teltonika RutOS integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    RutosAuthError,
    RutosClient,
    RutosConnectionError,
    RutosError,
)
from .const import (
    CONF_DEVICE_ID,
    CONF_MODEL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import TeltonikaConfigEntry

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        # RutOS ships a self-signed certificate, so verification is off by
        # default. Users with their own CA can switch it on.
        vol.Optional(CONF_VERIFY_SSL, default=False): bool,
    }
)


class TeltonikaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle setup and reauthentication."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialise the flow."""
        self._reauth_entry: TeltonikaConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect connection details and verify them."""
        errors: dict[str, str] = {}

        if user_input is not None:
            info, error = await self._async_try_connect(user_input)
            if error:
                errors["base"] = error
            else:
                identifier = info.get("device_identifier")
                if identifier:
                    await self.async_set_unique_id(identifier)
                    self._abort_if_unique_id_configured(
                        updates={CONF_HOST: user_input[CONF_HOST]}
                    )
                title = info.get("device_name") or info.get("device_model") or "Teltonika"
                return self.async_create_entry(
                    title=title,
                    data={
                        **user_input,
                        CONF_MODEL: info.get("device_model"),
                        CONF_DEVICE_ID: identifier,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication after the credentials stopped working."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for fresh credentials."""
        errors: dict[str, str] = {}
        entry = self._reauth_entry
        assert entry is not None

        if user_input is not None:
            candidate = {**entry.data, **user_input}
            _, error = await self._async_try_connect(candidate)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data=candidate)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=entry.data.get(CONF_USERNAME)): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={"host": entry.data.get(CONF_HOST, "")},
        )

    async def _async_try_connect(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, Any], str | None]:
        """Probe the device, then verify the credentials.

        Probing first means a wrong address is reported as such instead of
        surfacing as "invalid password", which is the more confusing of the
        two — ``unauthorized/status`` answers without any credentials.
        """
        client = RutosClient(
            async_get_clientsession(
                self.hass, verify_ssl=user_input.get(CONF_VERIFY_SSL, False)
            ),
            user_input[CONF_HOST],
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            verify_ssl=user_input.get(CONF_VERIFY_SSL, False),
        )

        try:
            info = await client.async_probe()
        except RutosConnectionError:
            return {}, "cannot_connect"
        except RutosError:
            return {}, "not_rutos"

        if not info.get("device_model"):
            return {}, "not_rutos"

        try:
            await client.async_verify_credentials()
        except RutosAuthError:
            return info, "invalid_auth"
        except RutosConnectionError:
            return info, "cannot_connect"
        except RutosError:
            _LOGGER.exception("Unexpected error verifying credentials")
            return info, "unknown"

        return info, None

    @staticmethod
    @callback
    def async_get_options_flow(entry: TeltonikaConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return TeltonikaOptionsFlow()


class TeltonikaOptionsFlow(OptionsFlowWithReload):
    """Let the user change the polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    )
                }
            ),
        )
