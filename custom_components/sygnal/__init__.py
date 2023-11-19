"""A sygnal/livezi chatterbox integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any


from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import config_flow  # noqa  pylint_disable=unused-import
from .chatterbox import SygnalApi, SygnalClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH, Platform.COVER, Platform.CLIMATE, Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sygnal from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    sygnal_connection = SygnalApi(SygnalClient(
        entry.data[CONF_HOST],
        async_get_clientsession(hass),
    ))
    sygnal_data_coordinator = SygnalDataUpdateCoordinator(
        hass,
        sygnal_connection=sygnal_connection,
    )
    await sygnal_data_coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = sygnal_data_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class SygnalDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Sygnal data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        sygnal_connection: chatterbox.SygnalApi,
    ) -> None:
        """Initialize global Sygnal data updater."""
        self.api = sygnal_connection

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data."""
        data = await self.api.async_update()
        #if data is None:
        #    raise update_coordinator.UpdateFailed(
        #        "Unable to connect to Sygnal device"
        #    )
        return self.api#data
