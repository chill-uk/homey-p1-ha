"""Config flow for the Homey P1 integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

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
            await self.async_set_unique_id(host.lower())
            self._abort_if_unique_id_configured()

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
