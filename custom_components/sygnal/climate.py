"""Support for the Livezi/Sygnal Chatterbox HVAC."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SygnalEntity

HVAC_MODE_TO_SYGNAL = {
    HVACMode.OFF: 'off',
    HVACMode.FAN_ONLY: 'vent',
    HVACMode.HEAT: 'heat',
    HVACMode.COOL: 'cool',
    HVACMode.HEAT_COOL: 'auto',
}
HVAC_MODE_FROM_SYGNAL = {v: k for k, v in HVAC_MODE_TO_SYGNAL.items()}

FAN_MODE_TO_SYGNAL = {
    FAN_AUTO:   'auto',
    FAN_LOW:    'low',
    FAN_MEDIUM: 'medium',
    FAN_HIGH:   'high',
}
FAN_MODE_FROM_SYGNAL = {v: k for k, v in FAN_MODE_TO_SYGNAL.items()}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sygnal climate platform."""
    async_add_entities(
        [SygnalClimate(hass.data[DOMAIN][config_entry.entry_id],
                       config_entry.unique_id)]
    )


class SygnalClimate(SygnalEntity, ClimateEntity):
    """Sygnal/Livezi/ZPlus AC unit."""

    _attr_has_entity_name = True
    _attr_name = "Aircon"
    _attr_fan_modes = list(FAN_MODE_TO_SYGNAL.keys())
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_max_temp = 30
    _attr_min_temp = 15
    _attr_hvac_modes = list(HVAC_MODE_TO_SYGNAL.keys())
    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE |
        ClimateEntityFeature.TARGET_TEMPERATURE
    )

    def __init__(self, coordinator: SygnalDataUpdateCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)

    @property
    def device_state_attributes(self):
        return {
            'outside_coil_temperature': self.coordinator.api.outside_coil_temperature,
            'inside_coil_temperature': self.coordinator.api.inside_coil_temperature,
            'compressor_loading': self.coordinator.api.compressor_loading,
        }

    @property
    def current_temperature(self):
        return self.coordinator.api.current_temperature

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.api.target_temperature

    @property
    def hvac_mode(self) -> HVACMode | None:
        if self.coordinator.api.hvac_mode in HVAC_MODE_FROM_SYGNAL:
            return HVAC_MODE_FROM_SYGNAL[self.coordinator.api.hvac_mode]
        else:
            return HVAC_MODE_HEAT_COOL

    @property
    def hvac_modes(self):
        return list(HVAC_MODE_TO_SYGNAL.keys())

    @property
    def hvac_action(self):
        return self.coordinator.api.status

    @property
    def fan_mode(self) -> str | None:
        if self.coordinator.api.fan_mode in FAN_MODE_FROM_SYGNAL:
            return FAN_MODE_FROM_SYGNAL[self.coordinator.api.fan_mode]
        else:

            return FAN_LOW

    @property
    def fan_modes(self):
        return list(FAN_MODE_TO_SYGNAL.keys())

    async def async_set_temperature(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_temperature(kwargs[ATTR_TEMPERATURE])

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self.coordinator.api.async_set_hvac_mode(HVAC_MODE_TO_SYGNAL[hvac_mode])

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self.coordinator.api.async_set_fan_mode(FAN_MODE_TO_SYGNAL[fan_mode])

    async def async_turn_on(self) -> None:
        await self.coordinator.api.async_turn_on()

    async def async_turn_off(self) -> None:
        await self.coordinator.api.async_turn_off()

    async def async_update(self):
        await self.coordinator.api.async_update()
