"""Sensors for Weber June: cavity temp/target, probe temps, mode."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GrillState
from .coordinator import WeberJuneCoordinator
from .entity import WeberJuneEntity


@dataclass(frozen=True, kw_only=True)
class WeberSensorDescription(SensorEntityDescription):
    value_fn: Callable[[GrillState], float | int | None]


SENSORS: tuple[WeberSensorDescription, ...] = (
    WeberSensorDescription(
        key="cavity_temp",
        translation_key="cavity_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda s: s.cavity_temp_c,
    ),
    WeberSensorDescription(
        key="cavity_target",
        translation_key="cavity_target",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        icon="mdi:target",
        value_fn=lambda s: s.cavity_target_c,
    ),
    WeberSensorDescription(
        key="mode",
        translation_key="mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:state-machine",
        value_fn=lambda s: s.mode,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: WeberJuneCoordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        WeberSensor(coordinator, desc) for desc in SENSORS
    ]
    # One probe temperature sensor per probe seen at setup (at least one).
    n = max(1, len(coordinator.data.probe_temps_c))
    entities += [WeberProbeSensor(coordinator, i) for i in range(n)]
    async_add_entities(entities)


class WeberSensor(WeberJuneEntity, SensorEntity):
    entity_description: WeberSensorDescription

    def __init__(self, coordinator: WeberJuneCoordinator, desc: WeberSensorDescription):
        super().__init__(coordinator, desc.key)
        self.entity_description = desc

    @property
    def available(self) -> bool:
        # Snapshots are the grill's last reported values; when it goes offline
        # they are stale, so mark the reading unavailable rather than frozen.
        return super().available and self.coordinator.data.online

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)


class WeberProbeSensor(WeberJuneEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:thermometer-probe"

    def __init__(self, coordinator: WeberJuneCoordinator, index: int):
        super().__init__(coordinator, f"probe_{index + 1}_temp")
        self._index = index
        self._attr_translation_key = "probe_temp"
        self._attr_translation_placeholders = {"index": str(index + 1)}

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.online

    @property
    def native_value(self) -> float | None:
        temps = self.coordinator.data.probe_temps_c
        return temps[self._index] if self._index < len(temps) else None
