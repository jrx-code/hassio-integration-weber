"""Config flow for Weber Connect (cloud, app-free)."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .api import (
    WeberAuthError,
    WeberClientCredentialsError,
    WeberConnectionError,
    WeberJuneClient,
)
from .const import (
    CONF_APPLIANCE_ID,
    CONF_COMPANION_ID,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from .helpers import resolve_client_credentials

_LOGGER = logging.getLogger(__name__)


class WeberJuneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the account refresh token; auto-discover the appliance id."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            refresh = user_input[CONF_REFRESH_TOKEN].strip()
            appliance = (user_input.get(CONF_APPLIANCE_ID) or "").strip().lower()
            client_id, client_secret = await self.hass.async_add_executor_job(
                resolve_client_credentials, self.hass.config.config_dir
            )
            client = WeberJuneClient(
                refresh_token=refresh, appliance_id=appliance,
                client_id=client_id, client_secret=client_secret,
            )
            try:
                await self.hass.async_add_executor_job(client.ensure_token)
                if not appliance:
                    appliance = await self.hass.async_add_executor_job(
                        client.discover_appliance_id
                    )
            except WeberClientCredentialsError:
                errors["base"] = "missing_client_credentials"
            except WeberAuthError:
                errors["base"] = "invalid_auth"
            except WeberConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if not appliance:
                    # Token is valid but the grill wasn't streaming, so we could
                    # not read the id — ask the user to supply it.
                    errors[CONF_APPLIANCE_ID] = "appliance_not_found"
                else:
                    await self.async_set_unique_id(appliance)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Weber Spirit ({appliance[:8]})",
                        data={
                            CONF_REFRESH_TOKEN: client.refresh_token,
                            CONF_APPLIANCE_ID: appliance,
                            CONF_COMPANION_ID: (
                                user_input.get(CONF_COMPANION_ID) or ""
                            ).strip(),
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REFRESH_TOKEN): str,
                    vol.Optional(CONF_APPLIANCE_ID, default=""): str,
                    vol.Optional(CONF_COMPANION_ID, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the companion id of an existing entry (model/serial lookup)."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data={
                    **entry.data,
                    CONF_COMPANION_ID: user_input[CONF_COMPANION_ID].strip(),
                },
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_COMPANION_ID,
                        default=entry.data.get(CONF_COMPANION_ID, ""),
                    ): str,
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """The stored refresh token stopped working; ask for a new one."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors: dict[str, str] = {}
        if user_input is not None:
            client_id, client_secret = await self.hass.async_add_executor_job(
                resolve_client_credentials, self.hass.config.config_dir
            )
            client = WeberJuneClient(
                refresh_token=user_input[CONF_REFRESH_TOKEN].strip(),
                appliance_id=entry.data[CONF_APPLIANCE_ID],
                client_id=client_id,
                client_secret=client_secret,
            )
            try:
                await self.hass.async_add_executor_job(client.ensure_token)
            except WeberClientCredentialsError:
                errors["base"] = "missing_client_credentials"
            except WeberAuthError:
                errors["base"] = "invalid_auth"
            except WeberConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_REFRESH_TOKEN: client.refresh_token},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_REFRESH_TOKEN): str}),
            errors=errors,
        )
