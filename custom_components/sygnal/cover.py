"""Platform for the Sygnal cover component."""
from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SygnalDataUpdateCoordinator
from .const import DOMAIN
from .entity import SygnalEntity

_LOGGER = logging.getLogger(__name__)

STATES_MAP = {0: STATE_CLOSED, 1: STATE_OPEN}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a cover for each zone damper."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [SygnalCover(coordinator, zone)
                for zone in coordinator.api.zones]
    async_add_entities(entities)


class SygnalCover(SygnalEntity, CoverEntity):

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = CoverDeviceClass.DAMPER
    _attr_supported_features = (
        CoverEntityFeature.OPEN |
        CoverEntityFeature.CLOSE |
        CoverEntityFeature.SET_POSITION
    )

    def __init__(self, coordinator: SygnalDataUpdateCoordinator, zone: str) -> None:
        self._zone = zone
        self._attr_name = zone
        super().__init__(coordinator, zone)

    async def async_close_cover(self, **kwargs: Any) -> None:
        if self._attr_is_closed:
            return
        self._attr_is_closed = True
        await self.coordinator.api.async_set_zone_state(self._zone, False)

    async def async_open_cover(self, **kwargs: Any) -> None:
        if not self._attr_is_closed:
            return
        self._attr_is_closed = False
        await self.coordinator.api.async_set_zone_state(self._zone, True)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_zone_damper_position(
            self._zone, kwargs[ATTR_POSITION])

    @callback
    def _update_attr(self) -> None:
        status = self.coordinator.api
        self._attr_is_closed = not self.coordinator.api.zone_state(self._zone)
        self._attr_current_cover_position = self.coordinator.api.zone_damper_position(
            self._zone)

        # self._attr_name = "Owen Bed"#status["name"]
        # state = STATES_MAP.get(status.get("zone"))  # type: ignore[arg-type]
        # self._state = state
