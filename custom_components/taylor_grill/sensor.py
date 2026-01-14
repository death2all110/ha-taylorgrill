"""Sensor platform for Taylor Grill."""
import logging
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.const import UnitOfTemperature, CONF_NAME
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_ID, 
    CONF_TEMP_UNIT, 
    DEFAULT_TEMP_UNIT, 
    DOMAIN,
    DEFAULT_NAME,
    CONF_MANUFACTURER,
    CONF_MODEL,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Taylor Grill sensors."""
    device_name = entry.options.get(CONF_NAME, entry.data.get(CONF_NAME, DEFAULT_NAME))
    device_id = entry.data[CONF_DEVICE_ID]
    manufacturer = entry.options.get(CONF_MANUFACTURER, entry.data.get(CONF_MANUFACTURER, DEFAULT_MANUFACTURER))
    model = entry.options.get(CONF_MODEL, entry.data.get(CONF_MODEL, DEFAULT_MODEL))
    
    temp_unit = entry.options.get(
        CONF_TEMP_UNIT, entry.data.get(CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT)
    )
    
    sensors = [
        TaylorSmokerSensor(hass, device_name, device_id, manufacturer, model, entry.entry_id, "Internal Probe", 0, temp_unit),
        TaylorSmokerSensor(hass, device_name, device_id, manufacturer, model, entry.entry_id, "External Probe 1", 1, temp_unit),
        TaylorSmokerSensor(hass, device_name, device_id, manufacturer, model, entry.entry_id, "External Probe 2", 2, temp_unit),
        TaylorSmokerSensor(hass, device_name, device_id, manufacturer, model, entry.entry_id, "External Probe 3", 3, temp_unit),
    ]
    
    async_add_entities(sensors)


class TaylorSmokerSensor(SensorEntity):
    """Representation of a Smoker Probe."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass, device_name, device_id, manufacturer, model, entry_id, probe_name, probe_index, temp_unit):
        """Initialize the sensor."""
        self.hass = hass
        self._attr_name = probe_name
        self._device_name = device_name
        self._device_id = device_id
        self._manufacturer = manufacturer
        self._model = model
        self._attr_unique_id = f"{entry_id}_probe_{probe_index}"
        self._probe_index = probe_index
        
        self._is_celsius = temp_unit == UnitOfTemperature.CELSIUS
        if self._is_celsius:
             self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        else:
             self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
        
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

    @property
    def device_info(self) -> DeviceInfo:
        """Return information to link this entity with the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer=self._manufacturer,
            model=self._model,
    )

    def _parse_status(self, payload):
        """Parse the binary status message for specific probes."""
        if self._probe_index == 0:
            _LOGGER.debug(f"RAW MQTT PACKET: {payload.hex()}")

        if len(payload) < 25 or payload[0] != 0xFA:
            return

        if payload[3] != 0x0E:
            return

        try:
            if self._probe_index == 0: start_byte = 22
            elif self._probe_index == 1: start_byte = 4
            elif self._probe_index == 2: start_byte = 7
            elif self._probe_index == 3: start_byte = 10
            else: return

            hundreds = payload[start_byte]
            tens = payload[start_byte + 1]
            units = payload[start_byte + 2]

            if hundreds > 5: 
                self._state = None
            elif hundreds <= 9 and tens <= 9 and units <= 9:
                raw_f = (hundreds * 100) + (tens * 10) + units
                
                if self._is_celsius:
                    self._state = round((raw_f - 32) / 1.8, 1)
                else:
                    self._state = raw_f
            
            self.async_write_ha_state()

        except IndexError:
            pass

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state