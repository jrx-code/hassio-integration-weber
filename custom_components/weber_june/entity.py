"""Base entity for Weber June."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import WeberJuneCoordinator


class WeberJuneEntity(CoordinatorEntity[WeberJuneCoordinator]):
    """Shared device info + coordinator wiring."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WeberJuneCoordinator, key: str):
        super().__init__(coordinator)
        appliance = coordinator.client.appliance_id
        self._attr_unique_id = f"{appliance}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, appliance)},
            manufacturer=MANUFACTURER,
            model="Spirit / June",
            name="Weber Spirit",
        )
