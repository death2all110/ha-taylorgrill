"""Switch platform for Taylor Grill."""
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_ID

_LOGGER = logging.getLogger(__name__)

# Binary Commands
CMD_ON = bytes.fromhex("fa06fe0101ff")
CMD_OFF = bytes.fromhex("fa06fe0102ff")

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Taylor Grill switch."""
    name = entry.data[CONF_NAME]
    device_id = entry.data[CONF_DEVICE_ID]
    
    async_add_entities([TaylorSmokerSwitch(hass, name, device_id, entry.entry_id)])


class TaylorSmokerSwitch(SwitchEntity):
    """Representation of the Smoker Power Switch."""

    _attr_has_entity_name = True
    _attr_name = "Power"
    
    def __init__(self, hass, device_name, device_id, entry_id):
        self.hass = hass
        self._attr_unique_id = f"{entry_id}_power_switch"
        
        self._topic_cmd = f"{device_id}/app2dev"
        self._topic_state = f"{device_id}/dev2app"
        self._is_on = False

    async def async_added_to_hass(self):
        """Subscribe to MQTT topics."""
        @callback
        def message_received(message):
            self._parse_status(message.payload)

        await mqtt.async_subscribe(
            self.hass, self._topic_state, message_received, encoding=None
        )

    def _parse_status(self, payload):
        """Parse status for On/Off state."""
        if len(payload) < 10 or payload[0] != 0xFA:
            return

        # Packet Type 0x0B contains the state
        if payload[3] == 0x0B:
            try:
                state_byte = payload[5]
                # 0x01 = Running, 0x06 = Startup, 0x02 = Shutdown
                if state_byte in [0x01, 0x06]:
                    self._is_on = True
                elif state_byte == 0x02:
                    self._is_on = False
                self.async_write_ha_state()
            except IndexError:
                pass

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await mqtt.async_publish(self.hass, self._topic_cmd, CMD_ON)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await mqtt.async_publish(self.hass, self._topic_cmd, CMD_OFF)
        self._is_on = False
        self.async_write_ha_state()