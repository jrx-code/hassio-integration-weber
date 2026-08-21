"""Update coordinator for the Weber June integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ApplianceDetails,
    GrillState,
    WeberAuthError,
    WeberConnectionError,
    WeberJuneClient,
)
from .const import CONF_REFRESH_TOKEN, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class WeberJuneCoordinator(DataUpdateCoordinator[GrillState]):
    """Polls the cloud and holds the last-known setpoint across gaps."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: WeberJuneClient):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.entry = entry
        self.client = client
        # Filled once during setup; device info falls back to static values when
        # the cloud cannot tell us the model.
        self.details = ApplianceDetails()
        self._last_target_c: float | None = None
        self._last_session: str | None = None

    async def async_load_details(self) -> None:
        self.details = await self.hass.async_add_executor_job(
            self.client.appliance_details
        )

    async def _async_update_data(self) -> GrillState:
        try:
            state: GrillState = await self.hass.async_add_executor_job(self.client.poll)
        except WeberAuthError as err:
            # The cloud can retire a refresh token; retrying forever would never
            # recover, so ask the user for a fresh one instead.
            raise ConfigEntryAuthFailed(f"authentication failed: {err}") from err
        except WeberConnectionError as err:
            raise UpdateFailed(f"cloud unreachable: {err}") from err

        # The cloud may hand back a rotated refresh token on any mint. It only
        # lives in the client until now, so persist it — otherwise the entry keeps
        # a token the cloud has already retired and auth dies on the next restart.
        self._persist_refresh_token()

        # A new cook session (grill reboot / new cook) drops any earlier setpoint,
        # so don't carry a stale target across sessions.
        if state.session_id and state.session_id != self._last_session:
            self._last_session = state.session_id
            self._last_target_c = None

        # The setpoint rides a best-effort stream that only pushes while the grill
        # is actively connected; within a session keep the last value we saw rather
        # than flapping to unknown between pushes.
        if state.cavity_target_c is not None:
            self._last_target_c = state.cavity_target_c
        elif self._last_target_c is not None:
            state.cavity_target_c = self._last_target_c
        return state

    def _persist_refresh_token(self) -> None:
        current = self.client.refresh_token
        if current and current != self.entry.data.get(CONF_REFRESH_TOKEN):
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={**self.entry.data, CONF_REFRESH_TOKEN: current},
            )
            _LOGGER.debug("Stored rotated refresh token")
