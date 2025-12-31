"""Climate platform for Taylor Grill."""
import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVACMode,
    ClimateEntityFeature,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
    CONF_NAME,
)
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
    """Set up the Taylor Grill climate platform."""
    
    # 1. Get User Input
    name = entry.data[CONF_NAME]
    device_id = entry.data[CONF_DEVICE_ID]
    
    # 2. Create the Entity
    async_add_entities([TaylorSmoker(hass, name, device_id, entry.entry_id)])


class TaylorSmoker(ClimateEntity):
    """Representation of the Smoker."""

    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = 180
    _attr_max_temp = 450
    _attr_target_temperature_step = 10

    def __init__(self, hass, name, device_id, unique_id):
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        
        # Build Topics Dynamically
        self._topic_cmd = f"{device_id}/app2dev"
        self._topic_state = f"{device_id}/dev2app"
        
        self._hvac_mode = HVACMode.OFF
        self._target_temp = 180
        self._current_temp = None

    async def async_added_to_hass(self):
        """Subscribe to MQTT topics."""
        @callback
        def message_received(message):
            self._parse_status(message.payload)

        await mqtt.async_subscribe(
            self.hass, self._topic_state, message_received, encoding=None
        )

    def _parse_status(self, payload):
        """Parse the binary status message."""
        # Basic Validation
        if len(payload) < 10 or payload[0] != 0xFA:
            return

        # Identify Packet Type using Byte 3
        # 0x0B = State Update (On/Off)
        # 0x0E = Sensor Update (Temperatures)
        packet_type = payload[3]

        # --- LOGIC FOR STATE PACKET (0x0B) ---
        if packet_type == 0x0B:
            # Byte 5 contains the State
            # 0x01 = Running
            # 0x02 = Shutdown/Fan Mode
            # 0x06 = Startup/Ignite
            try:
                state_byte = payload[5]
                if state_byte in [0x01, 0x06]:
                    self._hvac_mode = HVACMode.HEAT
                elif state_byte == 0x02:
                    self._hvac_mode = HVACMode.OFF
                self.async_write_ha_state()
            except IndexError:
                pass

        # --- LOGIC FOR SENSOR PACKET (0x0E) ---
        elif packet_type == 0x0E and len(payload) >= 25:
            # The Grill Temp is at the very end of the packet (Bytes 22, 23, 24)
            # Format: [Hundreds] [Tens] [Units]
            try:
                hundreds = payload[22]
                tens = payload[23]
                units = payload[24]
                
                # Sanity check to avoid reading garbage data
                if hundreds <= 9 and tens <= 9 and units <= 9:
                    self._current_temp = (hundreds * 100) + (tens * 10) + units
                    self.async_write_ha_state()
            except IndexError:
                pass

    @property
    def current_temperature(self):
        return self._current_temp

    @property
    def target_temperature(self):
        return self._target_temp

    @property
    def hvac_mode(self):
        return self._hvac_mode

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.HEAT:
            await mqtt.async_publish(self.hass, self._topic_cmd, CMD_ON)
            self._hvac_mode = HVACMode.HEAT
        else:
            await mqtt.async_publish(self.hass, self._topic_cmd, CMD_OFF)
            self._hvac_mode = HVACMode.OFF
        
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        
        target = int(temp)
        
        # Calculate Hundreds and Tens
        range_byte = target // 100
        offset_byte = (target % 100) // 10
        
        # Safety Clamps
        if range_byte > 5: range_byte = 5
        if range_byte < 1: range_byte = 1
        
        # Construct Packet: FA 09 FE 05 01 [R] [O] 00 FF
        packet = bytearray([0xFA, 0x09, 0xFE, 0x05, 0x01, range_byte, offset_byte, 0x00, 0xFF])
        
        await mqtt.async_publish(self.hass, self._topic_cmd, packet)
        self._target_temp = target
        self.async_write_ha_state()