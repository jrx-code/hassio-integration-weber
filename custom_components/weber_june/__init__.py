"""The Weber Spirit / June (cloud, app-free) integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import WeberJuneClient
from .const import CONF_APPLIANCE_ID, CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import WeberJuneCoordinator
from .helpers import resolve_client_credentials

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

type WeberJuneConfigEntry = ConfigEntry[WeberJuneCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: WeberJuneConfigEntry) -> bool:
    """Set up Weber June from a config entry."""
    client_id, client_secret = await hass.async_add_executor_job(
        resolve_client_credentials, hass.config.config_dir
    )
    client = WeberJuneClient(
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        appliance_id=entry.data[CONF_APPLIANCE_ID],
        client_id=client_id,
        client_secret=client_secret,
    )
    coordinator = WeberJuneCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WeberJuneConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
