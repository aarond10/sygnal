"""Platform for the Sygnal switch component."""
from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SygnalDataUpdateCoordinator
from .const import DOMAIN
from .entity import SygnalEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a switch for each zone."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [SygnalSwitch(coordinator, zone) for zone in coordinator.api.zones]
    async_add_entities(entities)

class SygnalSwitch(SygnalEntity, SwitchEntity):

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: SygnalDataUpdateCoordinator, zone: str) -> None:
        self._zone = zone
        self._attr_name = zone
        super().__init__(coordinator, zone)

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self._attr_is_on:
            return
        self._attr_is_on = True
        await self.coordinator.api.async_set_zone_state(self._zone, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        if not self._attr_is_on:
            return
        self._attr_is_on = False
        await self.coordinator.api.async_set_zone_state(self._zone, False)

    @callback
    def _update_attr(self) -> None:
        status = self.coordinator.api
        self._attr_is_on = self.coordinator.api.zone_state(self._zone)

