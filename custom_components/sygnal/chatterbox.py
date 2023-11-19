"""
Library for controlling a Livezi/Sygnal Chatterbox via it's Web UI JSON interface.

The interface here is the same as that used by a 2015 JQuery web interface.
This may not work with more recent devices. YMMV.

This is provided without warranty and I take no responsibility for what you do
with this code.
 """
from typing import Dict, List, Text

import asyncio
import datetime
import json
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

_DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

HVAC_OFF = 'off'
HVAC_VENT = 'vent'
HVAC_HEAT = 'heat'
HVAC_COOL = 'cool'
HVAC_AUTO = 'auto'

FAN_OFF = 'off'  # generally interpret this as 'undefined'.
FAN_ULTRA_LOW = 'ultra low'
FAN_LOW = 'low'
FAN_MEDIUM = 'medium'
FAN_HIGH = 'high'
FAN_AUTO = 'auto'


class InvalidArgument(Exception):
    """Raised if invalid arguments are provided to SygnalClient."""


class SygnalClient():
    """Low-level direct access to Sygnal chatterbox device.
       This exposes device information, VRAM, EEPROM and RTC.
    """
    def __init__(self, hostname: Text, client_session):
        self._hostname = hostname
        self._client_session = client_session

    @property
    def hostname(self):
        return self._hostname

    async def _post(self, data):
        try:
            response = await self._client_session.post(
                f"http://{self._hostname}/ZPlus/file.lvjson", data=data)
            data = json.loads(await response.text())
            return data
        except (aiohttp.ClientError, IndexError) as error:
            _LOGGER.error("Failed to read/write to chatterbox: %s", error)

    async def get_device_info(self) -> Dict:
        try:
            response = await self._client_session.get(
                f"http://{self._hostname}/lv-lan-cboxes.json")
            data = json.loads(await response.text())
            return data
        except (aiohttp.ClientError, IndexError) as error:
            _LOGGER.error("Failed to read chatterbox device info: %s", error)
            raise error

    async def async_read_vram(self, offset: int, length: int) -> List[int]:
        # Only if the *entire* value being read is in valid cache will we use
        # it.
        end = offset + length
        if offset < 0:
            raise InvalidArgument(f"Offset out of range: {offset}")
        if end < offset or end > 69:
            raise InvalidArgument(f"Length out of range: {length}")
        data = json.dumps({"method": "fetch", "params": [
                          {"table": "paray", "start": offset, 'marker': "rot0",
                           "length": length, "datatype": "bytes"}]})
        try:
            ret = (await self._post(data))[0]
            return ret['values']
        except Exception as error:
            _LOGGER.error("Failed to read chatterbox device: %s", error)
            raise error

    async def async_write_vram(self, offset: int, bitmask: int, value: int):
        """Set some bits of a byte at a specific offset in vram."""
        if offset < 0 or offset >= 69:
            raise InvalidArgument(f"Offset out of range: {offset}")
        if bitmask <= 0 or bitmask > 255:
            raise InvalidArgument(f"bitmask out of range: {bitmask}")
        if value < 0 or value > 255:
            raise InvalidArgument(f"value out of range: {value}")
        data = json.dumps({"method": "send_packet", "id": 1, "params": [
                          {"marker": "paw", 'cmd': 0, "data": [offset, bitmask, value]}]})
        await self._post(data)

    async def async_read_eeprom(self, offset: int, length: int) -> List[int]:
        end = offset + length
        if offset < 0:
            raise InvalidArgument(f"Offset out of range: {offset}")
        if end < offset or end > 150:
            raise InvalidArgument(f"Length out of range: {length}")
        data = json.dumps({"method": "fetch", "params": [
                          {"table": "ee", "start": offset, "marker": "rot1",
                           "length": length, "datatype": "bytes"}]})
        ret = await self._post(data)
        return ret

    async def async_write_eeprom(self, offset: int, length: int, value: List[int]) -> bool:
        end = offset + length
        if offset < 0:
            raise InvalidArgument(f"Offset out of range: {offset}")
        if end < offset or end > 150:
            raise InvalidArgument(f"Length out of range: {length}")
        # Can only write 4-byte aligned blocks.
        if length != 4 or offset % 4 or len(value) != 4:
            raise InvalidArgument('Can only write 4 byte aligned blocks.')
        data = json.dumps({'method': 'send_packet', 'id': 1, 'params': [
                          {'marker': "eew", 'cmd': 7, 'data': value}]})
        await self._post(data)

    async def async_read_rtc(self) -> datetime.datetime:
        data = json.dumps({'method': "fetch", 'params': [
                          {'table': "rtc", 'start': 0, 'marker': "rot3",
                           'length': 4, 'datatype': "bytes"}]})
        ret = await self._post(data)
        try:
            ret = ret[0]['values']
            return '%s %02d:%02d:%02d' % (
                _DAYS[ret[3]], ret[2], ret[1], ret[0])
        except (KeyError, IndexError) as error:
            _LOGGER.error("Error reading RTC: %s", error)
            return None

    async def async_write_rtc(self, now: datetime.datetime) -> bool:
        raise NotImplementedError()


class SygnalApi():
    """High-level access to Sygnal chatterbox device.
       This provides user-facing configuration, caches state, etc.
    """
    def __init__(self, client):
        self._client = client
        self._vram = [0] * 69
        self._eeprom = [0] * 150
        # self._rtc = "Mon 00:00:00"
        self._zones = {}
        self._device_info = {}

    async def _async_read_full_eeprom(self):
        eeprom = []
        while len(eeprom) < 150:
            end = min(150, len(eeprom) + 128)
            try:
                data = await self._client.async_read_eeprom(len(eeprom), end - len(eeprom))
                # Nb: Occasionally eeprom reads seem to fail, resulting in zero data
                # being returned. We need to take this into account or we can end up
                # with data at the wrong offsets.
                eeprom += data[0]['values']
            except (KeyError, IndexError) as error:
                _LOGGER.error(
                    "Exception reading EEPROM range [%s:%s]: %s", len(eeprom),end, error)
        return eeprom

    async def async_update(self):
        self._vram = await self._client.async_read_vram(0, 69)

        # The eeprom shouldn't change often so we don't bother refreshing it.
        if self._eeprom[0] == 0:
            self._eeprom = await self._async_read_full_eeprom()
            self._zones = {}
            for i in range(8):
                if self._zone_mask & (1 << i):
                    name = ''.join([chr(c)
                                   for c in self._eeprom[i * 8:(i + 1) * 8]]).rstrip()
                    self._zones[name] = i

        # self._rtc = await self._client.async_read_rtc()

        self._device_info = await self._client.get_device_info()

    async def async_write_vram(self, offset, mask, value):
        await self._client.async_write_vram(offset, mask, value)
        self._vram[offset] = self._vram[offset] & (0xff ^ mask)
        self._vram[offset] = self._vram[offset] | (mask & value)

    @property
    def name(self):
        return self._client.hostname

    @property
    def unique_id(self):
        return self._device_info['local']['mac'].replace(':', '')

    @property
    def device_info(self):
        return self._device_info

    @property
    def status(self):
        states = {
            0x01: 'Cooling',
            0x02: 'Heating',
            0x04: 'Run Timer',
            0x08: 'TC Running',
            0x10: 'Compressor Running',
            0x20: 'Compressor Fan Running',
            0x40: 'RV Running',              # RV = Relief Valve? Surely not...
            0x80: 'Crank Heater',
        }
        status = [states[1 << i]
                  for i in range(8) if self._vram[60] & (1 << i)]
        return 'Idle' if not status else ', '.join(status)

    @property
    def compressor_loading(self):
        """Percentage loading of digital scroll compressor"""
        return self._vram[62]

    @property
    def outside_coil_temperature(self):
        """External coil temperature (celsius)"""
        return self._vram[63] / 2.0

    @property
    def inside_coil_temperature(self):
        """Internal coil temperature (celsius)"""
        return self._vram[64] / 2.0

    @property
    def discharge_temperature(self):
        """???"""
        return self._vram[65] / 2.0

    @property
    def current_temperature(self):
        """Temperature at intake (celsius)"""
        return self._vram[67] / 2.0

    @property
    def target_temperature(self):
        value = self._vram[1]
        if value > 128:
            value -= 256
        return 22.5 + value / 2

    async def async_set_temperature(self, target_temp):
        value = float(target_temp)
        temp = int((value - 22.5) * 2)
        if temp < 0:
            temp += 256
        await self.async_write_vram(1, 255, temp)

    async def async_turn_on(self):
        await self.async_write_vram(0, 1, 1)

    async def async_turn_off(self):
        await self.async_write_vram(0, 1, 0)

    @classmethod
    def hvac_modes(cls):
        """The set of available HVAC modes."""
        return [HVAC_OFF, HVAC_VENT, HVAC_COOL, HVAC_HEAT, HVAC_AUTO]

    @property
    def hvac_mode(self):
        """The current HVAC mode (as a string)"""
        val_to_mode = {
            0x00: HVAC_VENT,
            0x40: HVAC_COOL,
            0x80: HVAC_HEAT,
            0xc0: HVAC_AUTO,
        }
        if not self._vram[0] & 0x01:
            return HVAC_OFF
        return val_to_mode[self._vram[0] & 0xc0]

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the HVAC mode"""
        hvac_mode_to_cmd = {
            HVAC_OFF: [0, 0x01, 0x00],
            HVAC_VENT: [0, 0xc1, 0x01],
            HVAC_COOL: [0, 0xc1, 0x41],
            HVAC_HEAT: [0, 0xc1, 0x81],
            HVAC_AUTO: [0, 0xc1, 0xc1],
        }
        await self.async_write_vram(*hvac_mode_to_cmd[hvac_mode])

    @classmethod
    def fan_modes(cls):
        """The set of available fan modes."""
        return [FAN_ULTRA_LOW, FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_AUTO]

    @property
    def fan_mode(self):
        """Returns the fan mode (as a string)"""
        cmd_to_fan_mode = {
            0x00: FAN_OFF,
            0x02: FAN_ULTRA_LOW,
            0x04: FAN_LOW,
            0x06: FAN_MEDIUM,
            0x08: FAN_HIGH,
            0x20: FAN_AUTO,
        }
        return cmd_to_fan_mode[self._vram[0] & 0x3e]

    async def async_set_fan_mode(self, fan_mode):
        """Sets the fan mode"""
        fan_mode_to_cmd = {
            FAN_ULTRA_LOW: [0, 0x3e, 0x02],
            FAN_LOW: [0, 0x3e, 0x04],
            FAN_MEDIUM: [0, 0x3e, 0x06],
            FAN_HIGH: [0, 0x3e, 0x08],
            FAN_AUTO: [0, 0x3e, 0x20],
        }
        await self.async_write_vram(*fan_mode_to_cmd[fan_mode])

    @property
    def _zone_mask(self):
        return self._vram[39]

    @property
    def zones(self):
        """The set of zone names"""
        return self._zones.keys()

    def zone_state(self, name: Text):
        """Read the on/off state for a given zone."""
        if name not in self._zones:
            raise InvalidArgument(f"Bad zone ({name} not in {self._zones})")
        index = self._zones[name]
        return self._vram[2 + index] & 0x80 != 0

    def zone_damper_position(self, name: Text):
        """Read the last measured actual damper position for a given zone."""
        if name not in self._zones:
            raise InvalidArgument(f"Bad zone ({name} not in {self._zones})")
        index = self._zones[name]
        return self._vram[47 + index]

    async def async_set_zone_damper_position(self, name: str, position: int):
        """Set the zone damper position (0-100) for when zone is enabled."""
        if name not in self._zones:
            raise InvalidArgument(f"Bad zone ({name} not in {self._zones})")
        index = self._zones[name]
        position = min(100, max(0, position))
        await self.async_write_vram(2 + index, 0x7f, position)

    async def async_set_zone_state(self, name: str, enabled: bool):
        """Enable/disable a given zone."""
        if name not in self._zones:
            raise InvalidArgument(f"Bad zone ({name} not in {self._zones})")
        index = self._zones[name]
        val = 0x80 if enabled else 0x00
        await self.async_write_vram(2 + index, 0x80, val)


if __name__ == "__main__":
    async def main():
        """Basic code exercises and debug output."""
        async with aiohttp.ClientSession() as session:
            api = SygnalApi(SygnalClient('chatterbox', session))

            await api.async_update()

            print('id', api.unique_id)
            print('device_info', api.device_info)
            print('status', api.status)
            print('current_temperature', api.current_temperature)
            print('target_temperature', api.target_temperature)
            print('compressor_loading', api.compressor_loading)
            print('outside_coil_temperature', api.outside_coil_temperature)
            print('inside_coil_temperature', api.inside_coil_temperature)
            print('discharge_temperature', api.discharge_temperature)
            print('hvac_mode', api.hvac_mode)
            print('fan_mode', api.fan_mode)
            print('zones', api.zones)
            for zone in api.zones:
                print(f"  {zone}: {api.zone_damper_position(zone)}")

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
