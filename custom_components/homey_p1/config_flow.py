"""Config flow for the Homey P1 integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    CannotConnectError,
    ConnectionLimitError,
    LocalAPIDisabledError,
    async_validate_connection,
)
from .const import DEFAULT_NAME, DOMAIN


class HomeyP1ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homey P1."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            errors = await _async_validate_host(self.hass, host)
            if not errors:
                self._abort_if_host_already_configured(host)

                return self.async_create_entry(
                    title=user_input[CONF_NAME].strip() or DEFAULT_NAME,
                    data={
                        CONF_HOST: host,
                        CONF_NAME: user_input[CONF_NAME].strip() or DEFAULT_NAME,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
            errors=errors,
        )

    def _abort_if_host_already_configured(self, host: str) -> None:
        """Abort if another entry already uses this host."""
        _abort_if_host_already_configured(
            None,
            self._async_current_entries(),
            host,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HomeyP1OptionsFlow:
        """Get the options flow for this handler."""
        return HomeyP1OptionsFlow(config_entry)


class HomeyP1OptionsFlow(config_entries.OptionsFlow):
    """Handle Homey P1 options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Manage integration options."""
        errors: dict[str, str] = {}
        current_host = self.config_entry.options.get(
            CONF_HOST,
            self.config_entry.data[CONF_HOST],
        )

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            errors = await _async_validate_host(self.hass, host)
            if not errors:
                _abort_if_host_already_configured(
                    self.config_entry,
                    self.hass.config_entries.async_entries(DOMAIN),
                    host,
                )
                return self.async_create_entry(
                    title="",
                    data={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=current_host): str,
                }
            ),
            errors=errors,
        )


async def _async_validate_host(
    hass: HomeAssistant,
    host: str,
) -> dict[str, str]:
    """Validate a websocket host and map errors to config flow strings."""
    try:
        await async_validate_connection(
            async_get_clientsession(hass),
            host,
        )
    except LocalAPIDisabledError:
        return {"base": "local_api_disabled"}
    except ConnectionLimitError:
        return {"base": "connection_limit"}
    except CannotConnectError:
        return {"base": "cannot_connect"}

    return {}


def _abort_if_host_already_configured(
    current_entry: config_entries.ConfigEntry | None,
    entries: list[config_entries.ConfigEntry],
    host: str,
) -> None:
    """Abort if another entry already uses this host."""
    normalized_host = host.strip().lower()
    for entry in entries:
        if current_entry is not None and entry.entry_id == current_entry.entry_id:
            continue

        configured_host = entry.options.get(
            CONF_HOST,
            entry.data.get(CONF_HOST, ""),
        ).strip().lower()
        if configured_host == normalized_host:
            raise config_entries.AbortFlow("already_configured")
