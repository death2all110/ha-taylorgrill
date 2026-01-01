"""Sensor platform for Taylor Grill."""
import logging
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, CONF_NAME
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_ID

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Taylor Grill sensors."""
    name = entry.data[CONF_NAME]
    device_id = entry.data[CONF_DEVICE_ID]
    
    # Create 4 Sensors
    sensors = [
        TaylorSmokerSensor(hass, name, device_id, entry.entry_id, "Internal Probe", 1),
        TaylorSmokerSensor(hass, name, device_id, entry.entry_id, "Probe 2", 2),
        TaylorSmokerSensor(hass, name, device_id, entry.entry_id, "Probe 3", 3),
        TaylorSmokerSensor(hass, name, device_id, entry.entry_id, "Probe 4", 4),
    ]
    
    async_add_entities(sensors)


class TaylorSmokerSensor(SensorEntity):
    """Representation of a Smoker Probe."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT

    def __init__(self, hass, device_name, device_id, entry_id, probe_name, probe_index):
        """Initialize the sensor."""
        self.hass = hass
        self._attr_name = probe_name
        self._attr_unique_id = f"{entry_id}_probe_{probe_index}"
        self._probe_index = probe_index
        
        # Topic to listen to
        self._topic_state = f"{device_id}/dev2app"
        self._state = None

    async def async_added_to_hass(self):
        """Subscribe to MQTT topics."""
        @callback
        def message_received(message):
            self._parse_status(message.payload)

        await mqtt.async_subscribe(
            self.hass, self._topic_state, message_received, encoding=None
        )

    def _parse_status(self, payload):
        """Parse the binary status message for specific probes."""
        # Validation
        if len(payload) < 25 or payload[0] != 0xFA:
            return

        # Check packet type (must be 0x0E for Sensors)
        if payload[3] != 0x0E:
            return

        # BYTE MAPPING (Based on Triplet Logic)
        # Probe 1 (Internal): Bytes 22, 23, 24
        # Probe 2: Bytes 4, 5, 6
        # Probe 3: Bytes 7, 8, 9
        # Probe 4: Bytes 10, 11, 12
        
        try:
            if self._probe_index == 1:
                start_byte = 22
            elif self._probe_index == 2:
                start_byte = 4
            elif self._probe_index == 3:
                start_byte = 7
            elif self._probe_index == 4:
                start_byte = 10
            else:
                return

            hundreds = payload[start_byte]
            tens = payload[start_byte + 1]
            units = payload[start_byte + 2]

            # Filter Garbage Data (e.g., 960F usually means unplugged)
            if hundreds > 5: 
                self._state = None
            elif hundreds <= 9 and tens <= 9 and units <= 9:
                self._state = (hundreds * 100) + (tens * 10) + units
            
            self.async_write_ha_state()

        except IndexError:
            pass

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state