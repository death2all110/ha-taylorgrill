"""Climate platform for Taylor Grill."""
import logging
import asyncio
from datetime import timedelta
import voluptuous as vol

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
from homeassistant.helpers import config_validation as cv

from .const import CONF_DEVICE_ID, CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT

_LOGGER = logging.getLogger(__name__)

# --- COMMANDS ---
CMD_ON = bytes.fromhex("fa06fe0101ff")
CMD_OFF = bytes.fromhex("fa06fe0102ff")
CMD_POLL_STATUS = bytes.fromhex("fa06fe0b01ff")
CMD_POLL_TEMPS  = bytes.fromhex("fa06fe0e01ff")
CMD_POLL_TARGET = bytes.fromhex("fa06fe0d01ff")
CMD_HANDSHAKE   = bytes.fromhex("fa06fe5f01ff")

# Standard QoS 0 is sufficient and reliable for this device
MQTT_QOS_CMD = 0
MQTT_RETAIN_CMD = False

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Taylor Grill climate platform."""
    name = entry.data[CONF_NAME]
    device_id = entry.data[CONF_DEVICE_ID]
    
    # Hardcoded to 2 seconds to match Android App heartbeat
    poll_interval = 2
    
    temp_unit = entry.options.get(
        CONF_TEMP_UNIT, entry.data.get(CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT)
    )
    
    smoker = TaylorSmoker(hass, name, device_id, entry.entry_id, poll_interval, temp_unit)
    async_add_entities([smoker])


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
        
        if self._is_celsius:
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
            self._attr_min_temp = 82
            self._attr_max_temp = 260
            self._attr_target_temperature_step = 1
            self._target_temp = 177
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
        
        # Initial Wakeup
        await mqtt.async_publish(self.hass, self._topic_cmd, CMD_HANDSHAKE, qos=MQTT_QOS_CMD, retain=MQTT_RETAIN_CMD)

        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._run_poll_cycle, timedelta(seconds=self._poll_interval)
            )
        )

    async def _run_poll_cycle(self, now=None):
        """
        Android App Heartbeat Sequence:
        Handshake -> Status -> Temps -> Target
        """
        # 1. Unlock/Handshake
        await mqtt.async_publish(self.hass, self._topic_cmd, CMD_HANDSHAKE, qos=MQTT_QOS_CMD, retain=MQTT_RETAIN_CMD)
        await asyncio.sleep(0.2)
        
        # 2. Poll Status (On/Off)
        await mqtt.async_publish(self.hass, self._topic_cmd, CMD_POLL_STATUS, qos=MQTT_QOS_CMD, retain=MQTT_RETAIN_CMD)
        await asyncio.sleep(0.2)
        
        # 3. Poll Current Probes
        await mqtt.async_publish(self.hass, self._topic_cmd, CMD_POLL_TEMPS, qos=MQTT_QOS_CMD, retain=MQTT_RETAIN_CMD)
        await asyncio.sleep(0.2)
        
        # 4. Poll Target Temp
        await mqtt.async_publish(self.hass, self._topic_cmd, CMD_POLL_TARGET, qos=MQTT_QOS_CMD, retain=MQTT_RETAIN_CMD)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature immediately."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        
        target_val = int(temp)
        
        if self._is_celsius:
            target_f = int((target_val * 1.8) + 32)
        else:
            target_f = target_val
        
        range_byte = target_f // 100
        offset_byte = (target_f % 100) // 10
        units_byte = target_f % 10
        
        if range_byte > 5: range_byte = 5
        if range_byte < 1: range_byte = 1
        
        # CRITICAL: Convert to immutable bytes() before sending
        packet = bytes([0xFA, 0x09, 0xFE, 0x05, 0x01, range_byte, offset_byte, units_byte, 0xFF])
        
        _LOGGER.debug(f"User Changed Target Temp to {target_val} ({target_f}F). Sending MQTT RAW BYTES: {packet.hex()}")
        await mqtt.async_publish(self.hass, self._topic_cmd, packet, qos=MQTT_QOS_CMD, retain=MQTT_RETAIN_CMD)
        
        # Optimistically update the UI
        self._target_temp = target_val
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set ON/OFF immediately."""
        if hvac_mode == HVACMode.HEAT:
            _LOGGER.debug(f"User turned Smoker ON. Sending: {CMD_ON.hex()}")
            await mqtt.async_publish(self.hass, self._topic_cmd, CMD_ON, qos=MQTT_QOS_CMD, retain=MQTT_RETAIN_CMD)
            self._hvac_mode = HVACMode.HEAT
        else:
            _LOGGER.debug(f"User turned Smoker OFF. Sending: {CMD_OFF.hex()}")
            await mqtt.async_publish(self.hass, self._topic_cmd, CMD_OFF, qos=MQTT_QOS_CMD, retain=MQTT_RETAIN_CMD)
            self._hvac_mode = HVACMode.OFF
        self.async_write_ha_state()

    def _parse_status(self, payload):
        """Parse the binary status message."""
        if len(payload) < 6 or payload[0] != 0xFA:
            return

        # --- Status Packet (0x0B) ---
        if b'\xFE\x0B' in payload:
            try:
                idx = payload.find(b'\xFE\x0B')
                if idx != -1 and idx + 3 < len(payload):
                    state_byte = payload[idx + 3]
                    # 0x02 is OFF. 0x01 (Startup) and 0x06 (Running) are ON.
                    if state_byte == 0x02:
                        if self._hvac_mode != HVACMode.OFF:
                            _LOGGER.debug(f"Smoker reports Status: OFF (Byte: {state_byte})")
                        self._hvac_mode = HVACMode.OFF
                    else:
                        if self._hvac_mode != HVACMode.HEAT:
                            _LOGGER.debug(f"Smoker reports Status: ON (Byte: {state_byte})")
                        self._hvac_mode = HVACMode.HEAT
                    self.async_write_ha_state()
            except IndexError:
                pass

        # --- Sensor Packet (0x0E) ---
        if b'\xFE\x0E' in payload:
            try:
                idx = payload.find(b'\xFE\x0E')
                # Parse up to 4 probes for logging
                # Offset mapping: Internal(+20), P1(+23), P2(+26), P3(+29)
                base = idx + 20
                if base + 2 < len(payload):
                    # Internal
                    h, t, u = payload[base], payload[base+1], payload[base+2]
                    raw_int = (h * 100) + (t * 10) + u
                    
                    # Log other probes if available
                    log_msg = f"Smoker reports Internal Temp: {raw_int}F"
                    
                    # Try P1
                    if base + 5 < len(payload):
                        h1, t1, u1 = payload[base+3], payload[base+4], payload[base+5]
                        raw_p1 = (h1 * 100) + (t1 * 10) + u1
                        log_msg += f", Probe 1: {raw_p1}F"
                        
                    # Try P2
                    if base + 8 < len(payload):
                        h2, t2, u2 = payload[base+6], payload[base+7], payload[base+8]
                        raw_p2 = (h2 * 100) + (t2 * 10) + u2
                        log_msg += f", Probe 2: {raw_p2}F"

                    _LOGGER.debug(log_msg)

                    # Update Entity State (Internal Probe)
                    if self._is_celsius:
                        self._current_temp = round((raw_int - 32) / 1.8)
                    else:
                        self._current_temp = raw_int
                    self.async_write_ha_state()
            except (IndexError, ValueError):
                pass

        # --- Target Temp Packet (0x0D) ---
        if b'\xFE\x0D' in payload:
            try:
                idx = payload.find(b'\xFE\x0D')
                if idx != -1 and idx + 22 < len(payload):
                    hundreds = payload[idx + 20]
                    tens = payload[idx + 21]
                    units = payload[idx + 22]
                    
                    if hundreds <= 9:
                        raw_target = (hundreds * 100) + (tens * 10) + units
                        
                        if self._is_celsius:
                            new_target = round((raw_target - 32) / 1.8)
                        else:
                            new_target = raw_target
                        
                        if new_target > 0:
                            # Check if changed externally
                            if self._target_temp != new_target:
                                _LOGGER.debug(f"Target temp changed outside of HA (or confirmed). Updating UI. New temp: {new_target}")
                                self._target_temp = new_target
                                self.async_write_ha_state()
            except (IndexError, ValueError):
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
