"""Config flow for the Homey P1 integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .api import (
    CannotConnectError,
    ConnectionLimitError,
    EncryptionKeyRequiredError,
    InvalidKeyError,
    LocalAPIDisabledError,
    async_validate_connection,
)
from .const import (
    CONF_AUTHENTICATION_KEY,
    CONF_ENCRYPTED_DIAGNOSTIC_CAPTURE,
    CONF_ENCRYPTION_KEY,
    DEFAULT_NAME,
    DOMAIN,
)
from .decryption import normalize_key


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
            self._abort_if_host_already_configured(host)
            keys = _clean_keys(user_input)
            errors = await _async_validate_host(self.hass, host, keys)
            if not errors:
                name = user_input.get(CONF_NAME, "").strip() or DEFAULT_NAME
                return self.async_create_entry(
                    title=name,
                    data={CONF_HOST: host, CONF_NAME: name, **keys},
                )

        defaults = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
                    vol.Optional(
                        CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Optional(
                        CONF_ENCRYPTION_KEY,
                        description={
                            "suggested_value": defaults.get(CONF_ENCRYPTION_KEY)
                        },
                    ): str,
                    vol.Optional(
                        CONF_AUTHENTICATION_KEY,
                        description={
                            "suggested_value": defaults.get(CONF_AUTHENTICATION_KEY)
                        },
                    ): str,
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
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HomeyP1OptionsFlow:
        """Get the options flow for this handler."""
        return HomeyP1OptionsFlow()


class HomeyP1OptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle Homey P1 options."""

    async def async_step_init(
        self, user_input: dict[str, str | bool] | None = None
    ) -> FlowResult:
        """Manage integration options."""
        errors: dict[str, str] = {}
        current_host = self.config_entry.options.get(
            CONF_HOST,
            self.config_entry.data[CONF_HOST],
        )
        current_keys = {
            key: self.config_entry.options.get(key, self.config_entry.data.get(key, ""))
            for key in (CONF_ENCRYPTION_KEY, CONF_AUTHENTICATION_KEY)
        }

        current_capture = self.config_entry.options.get(
            CONF_ENCRYPTED_DIAGNOSTIC_CAPTURE, False
        )

        if user_input is not None:
            capture = bool(user_input.get(CONF_ENCRYPTED_DIAGNOSTIC_CAPTURE, False))
            host = str(user_input[CONF_HOST]).strip()
            keys = _clean_keys(user_input)
            _abort_if_host_already_configured(
                self.config_entry,
                self.hass.config_entries.async_entries(DOMAIN),
                host,
            )

            unchanged = host.strip().lower() == current_host.strip().lower() and all(
                keys.get(key, "") == (current_keys[key] or "")
                for key in current_keys
            )
            if not unchanged:
                errors = await _async_validate_host(self.hass, host, keys)
            if not errors:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_HOST: host,
                        CONF_ENCRYPTED_DIAGNOSTIC_CAPTURE: capture,
                        CONF_ENCRYPTION_KEY: keys.get(CONF_ENCRYPTION_KEY, ""),
                        CONF_AUTHENTICATION_KEY: keys.get(CONF_AUTHENTICATION_KEY, ""),
                    },
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=current_host): str,
                    vol.Optional(
                        CONF_ENCRYPTION_KEY,
                        description={"suggested_value": current_keys[CONF_ENCRYPTION_KEY]},
                    ): str,
                    vol.Optional(
                        CONF_AUTHENTICATION_KEY,
                        description={
                            "suggested_value": current_keys[CONF_AUTHENTICATION_KEY]
                        },
                    ): str,
                    vol.Required(
                        CONF_ENCRYPTED_DIAGNOSTIC_CAPTURE, default=current_capture
                    ): selector.BooleanSelector(),
                }
            ),
            errors=errors,
        )


def _clean_keys(user_input: dict) -> dict[str, str]:
    """Return non-empty key fields as compact upper-case hex strings."""
    keys: dict[str, str] = {}
    for field in (CONF_ENCRYPTION_KEY, CONF_AUTHENTICATION_KEY):
        raw = str(user_input.get(field) or "")
        cleaned = "".join(ch for ch in raw if ch not in " \t\r\n:-").upper()
        if cleaned:
            keys[field] = cleaned
    return keys


async def _async_validate_host(
    hass: HomeAssistant,
    host: str,
    keys: dict[str, str] | None = None,
) -> dict[str, str]:
    """Validate a websocket host and map errors to config flow strings."""
    keys = keys or {}
    try:
        encryption_key = normalize_key(keys.get(CONF_ENCRYPTION_KEY))
        authentication_key = normalize_key(keys.get(CONF_AUTHENTICATION_KEY))
    except ValueError:
        return {"base": "invalid_key_format"}
    if authentication_key is not None and encryption_key is None:
        return {"base": "encryption_key_required"}

    try:
        await async_validate_connection(
            async_get_clientsession(hass),
            host,
            encryption_key,
            authentication_key,
        )
    except LocalAPIDisabledError:
        return {"base": "local_api_disabled"}
    except ConnectionLimitError:
        return {"base": "connection_limit"}
    except EncryptionKeyRequiredError:
        return {"base": "encryption_key_required"}
    except InvalidKeyError:
        return {"base": "invalid_encryption_key"}
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
