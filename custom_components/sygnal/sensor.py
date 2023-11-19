"""Platform for the Sygnal sensor component."""
from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SygnalDataUpdateCoordinator
from .const import DOMAIN
from .entity import SygnalEntity

_LOGGER = logging.getLogger(__name__)

SENSORS: [SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="outside_coil_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="inside_coil_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="discharge_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="compressor_loading",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [SygnalSensor(coordinator, desc) for desc in SENSORS]
    async_add_entities(entities)


class SygnalSensor(SygnalEntity, SensorEntity):
    """This class is for sensors exposing aircon internal state."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: SygnalDataUpdateCoordinator,
                 description: SensorEntityDescription) -> None:
        self.entity_description = description
        self._attr_name = description.key
        super().__init__(coordinator, description.key)

    @callback
    def _update_attr(self) -> None:
        self._attr_native_value = getattr(
            self.coordinator.api, self.entity_description.key)
