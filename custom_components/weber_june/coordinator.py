"""Update coordinator for the Weber June integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GrillState, WeberAuthError, WeberConnectionError, WeberJuneClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

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
        self._last_target_c: float | None = None
        self._last_session: str | None = None

    async def _async_update_data(self) -> GrillState:
        try:
            state: GrillState = await self.hass.async_add_executor_job(self.client.poll)
        except WeberAuthError as err:
            raise UpdateFailed(f"authentication failed: {err}") from err
        except WeberConnectionError as err:
            raise UpdateFailed(f"cloud unreachable: {err}") from err

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
