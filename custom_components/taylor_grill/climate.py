"""Climate platform for Taylor Grill."""
import logging
from datetime import timedelta
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
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_DEVICE_ID, CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT

_LOGGER = logging.getLogger(__name__)

# --- COMMANDS ---
CMD_ON = bytes.fromhex("fa06fe0101ff")
CMD_OFF = bytes.fromhex("fa06fe0102ff")
CMD_POLL_STATUS = bytes.fromhex("fa06fe0b01ff")
CMD_POLL_TEMPS  = bytes.fromhex("fa06fe0e01ff")
CMD_POLL_TARGET = bytes.fromhex("fa06fe0d01ff")
CMD_HANDSHAKE   = bytes.fromhex("fa06fe5f01ff")

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Taylor Grill climate platform."""
    name = entry.data[CONF_NAME]
    device_id = entry.data[CONF_DEVICE_ID]

    poll_interval = entry.options.get(
        CONF_POLL_INTERVAL, entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    )
    temp_unit = entry.options.get(
        CONF_TEMP_UNIT, entry.data.get(CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT)
    )
    
    if poll_interval < 5:
        poll_interval = 5
    
    async_add_entities([TaylorSmoker(hass, name, device_id, entry.entry_id, poll_interval, temp_unit)])


class TaylorSmoker(ClimateEntity):
    """Representation of the Smoker."""

    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, hass, name, device_id, unique_id, poll_interval, temp_unit):
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._poll_interval = poll_interval
        self._is_celsius = temp_unit == UnitOfTemperature.CELSIUS
        
        # Configure Units & Limits based on selection
        if self._is_celsius:
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
            self._attr_min_temp = 82  # Approx 180F
            self._attr_max_temp = 260 # Approx 500F
            self._attr_target_temperature_step = 1
            self._target_temp = 177 # Approx 350F
        else:
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
            self._attr_min_temp = 180
            self._attr_max_temp = 500
            self._attr_target_temperature_step = 5
            self._target_temp = 350

        self._topic_cmd = f"{device_id}/app2dev"
        self._topic_state = f"{device_id}/dev2app"
        
        self._hvac_mode = HVACMode.OFF
        self._current_temp = None

    async def async_added_to_hass(self):
        """Subscribe to MQTT topics and start polling."""
        @callback
        def message_received(message):
            self._parse_status(message.payload)

        await mqtt.async_subscribe(
            self.hass, self._topic_state, message_received, encoding=None
        )
        
        _LOGGER.debug(f"Sending Handshake: {CMD_HANDSHAKE.hex()}")
        await mqtt.async_publish(self.hass, self._topic_cmd, CMD_HANDSHAKE)

        _LOGGER.debug(f"Starting Polling Loop ({self._poll_interval}s)")
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._send_poll_commands, timedelta(seconds=self._poll_interval)
            )
        )

    async def _send_poll_commands(self, now=None):
        """Send polling commands."""
        await mqtt.async_publish(self.hass, self._topic_cmd, CMD_POLL_STATUS)
        await mqtt.async_publish(self.hass, self._topic_cmd, CMD_POLL_TEMPS)
        await mqtt.async_publish(self.hass, self._topic_cmd, CMD_POLL_TARGET)

    def _parse_status(self, payload):
        """Parse the binary status message (handling multiple packets)."""
        # 1. Always log the raw data first
        _LOGGER.debug(f"RAW MQTT PACKET (Climate): {payload.hex()}")

        if len(payload) < 10 or payload[0] != 0xFA:
            return

        # --- Parse Status (On/Off) ---
        if len(payload) >= 6 and payload[3] == 0x0B:
            try:
                state_byte = payload[5]
                if state_byte in [0x01, 0x06]:
                    self._hvac_mode = HVACMode.HEAT
                elif state_byte == 0x02:
                    self._hvac_mode = HVACMode.OFF
                self.async_write_ha_state()
            except IndexError:
                pass

        # --- Parse Current Temps (0x0E) ---
        if 0x0E in payload:
            try:
                idx = payload.find(b'\x0E')
                if idx != -1 and idx + 21 < len(payload):
                    hundreds = payload[idx + 19]
                    tens = payload[idx + 20]
                    units = payload[idx + 21]
                    
                    if hundreds <= 9 and tens <= 9 and units <= 9:
                        raw_f = (hundreds * 100) + (tens * 10) + units
                        if self._is_celsius:
                            self._current_temp = round((raw_f - 32) / 1.8)
                        else:
                            self._current_temp = raw_f
                        self.async_write_ha_state()
            except (IndexError, ValueError):
                pass

        # --- Parse Target Temp (0x0D)
        if 0x0D in payload:
            try:
                # Log that we found the signature
                _LOGGER.debug("Found hidden Target Temp packet (0x0D) in stack!")

                idx = payload.find(b'\x0D')
                if idx != -1 and idx + 24 < len(payload):
                    hundreds = payload[idx + 22]
                    tens = payload[idx + 23]
                    units = payload[idx + 24]
                    
                    if hundreds <= 9:
                        raw_target = (hundreds * 100) + (tens * 10) + units
                        
                        if raw_target > 0:
                            if self._is_celsius:
                                self._target_temp = round((raw_target - 32) / 1.8)
                            else:
                                self._target_temp = raw_target
                            
                            # Log the value we parsed
                            _LOGGER.debug(f"Parsed Target Temp from hidden packet: {self._target_temp}")
                            self.async_write_ha_state()
                            
            except (IndexError, ValueError) as e:
                _LOGGER.error(f"Error parsing target temp: {e}")

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
            _LOGGER.debug(f"Sending ON Command: {CMD_ON.hex()}")
            await mqtt.async_publish(self.hass, self._topic_cmd, CMD_ON)
            self._hvac_mode = HVACMode.HEAT
        else:
            _LOGGER.debug(f"Sending OFF Command: {CMD_OFF.hex()}")
            await mqtt.async_publish(self.hass, self._topic_cmd, CMD_OFF)
            self._hvac_mode = HVACMode.OFF
        
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        
        target_val = int(temp)
        
        # If in Celsius mode, convert back to Fahrenheit for the grill
        if self._is_celsius:
            target_f = int((target_val * 1.8) + 32)
        else:
            target_f = target_val
        
        range_byte = target_f // 100
        offset_byte = (target_f % 100) // 10
        units_byte = target_f % 10
        
        if range_byte > 5: range_byte = 5
        if range_byte < 1: range_byte = 1
        
        packet = bytearray([0xFA, 0x09, 0xFE, 0x05, 0x01, range_byte, offset_byte, units_byte, 0xFF])
        
        _LOGGER.debug(f"Sending Set Temp {target_val} ({target_f}F) Command: {packet.hex()}")
        
        await mqtt.async_publish(self.hass, self._topic_cmd, packet)
        self._target_temp = target_val
        self.async_write_ha_state()