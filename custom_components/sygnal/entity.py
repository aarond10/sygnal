"""Entity for the sygnal component."""
from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, SygnalDataUpdateCoordinator


class SygnalEntity(CoordinatorEntity[SygnalDataUpdateCoordinator]):
    """Representation of a Sygnal entity."""

    def __init__(
        self,
        sygnal_data_coordinator: SygnalDataUpdateCoordinator,
        device_id: str,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(sygnal_data_coordinator)

        if description is not None:
            self.entity_description = description
            self._attr_unique_id = f"{device_id}_{description.key}"
        else:
            self._attr_unique_id = device_id

        self._device_id = device_id
        self._update_attr()

    @callback
    def _update_attr(self) -> None:
        """Update the state and attributes."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        local = self.coordinator.api.device_info.get("local")
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, local["mac"])},
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Sygnal",
            name=local["device"],
            sw_version=local["version"],
        )
