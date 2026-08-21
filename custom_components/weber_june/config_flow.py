"""Config flow for Weber Spirit / June (cloud, app-free)."""
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
from .const import CONF_APPLIANCE_ID, CONF_REFRESH_TOKEN, DOMAIN
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
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REFRESH_TOKEN): str,
                    vol.Optional(CONF_APPLIANCE_ID, default=""): str,
                }
            ),
            errors=errors,
        )
