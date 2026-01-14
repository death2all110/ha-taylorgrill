"""Binary sensor platform for Taylor Grill."""
import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_ID,
    DOMAIN,
    DEFAULT_NAME,
    CONF_MANUFACTURER,
    CONF_MODEL,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL
)

_LOGGER = logging.getLogger(__name__)

# Error Mapping based on GrillWorkActivity.java
# Using TAMPER class to ensure UI says "Detected" (On) / "Clear" (Off) instead of "Problem"/"OK"

SENSORS_CONFIG = [
    {
        "name": "No Pellets",
        "key": "no_pellets",
        "offset": 11,
        "device_class": BinarySensorDeviceClass.TAMPER, 
        "icon": "mdi:beaker-alert-outline",
    },
    {
        "name": "Fan Error",
        "key": "fan_error",
        "offset": 8,
        "device_class": BinarySensorDeviceClass.TAMPER,
        "icon": "mdi:fan-alert",
    },
    {
        "name": "Auger Motor Error",
        "key": "auger_error",
        "offset": 10,
        "device_class": BinarySensorDeviceClass.TAMPER,
        "icon": "mdi:engine-off-outline",
    },
    {
        "name": "Ignition Error",
        "key": "ignition_error",
        "offset": 9,
        "device_class": BinarySensorDeviceClass.TAMPER,
        "icon": "mdi:fire-alert",
    },
    {
        "name": "High Temp Alert",
        "key": "high_temp_error",
        "offset": 7,
        "device_class": BinarySensorDeviceClass.HEAT, # Keeps "Hot" / "Normal" which is semantically nice
        "icon": "mdi:thermometer-alert",
    },
    {
        "name": "System Error 1",
        "key": "error_1",
        "offset": 4,
        "device_class": BinarySensorDeviceClass.TAMPER,
        "icon": "mdi:alert-circle",
    },
    {
        "name": "System Error 2",
        "key": "error_2",
        "offset": 5,
        "device_class": BinarySensorDeviceClass.TAMPER,
        "icon": "mdi:alert-circle",
    },
    {
        "name": "System Error 3",
        "key": "error_3",
        "offset": 6,
        "device_class": BinarySensorDeviceClass.TAMPER,
        "icon": "mdi:alert-circle",
    },
]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Taylor Grill binary sensors."""
    # Use custom name if set, otherwise fallback to default
    device_name = entry.options.get(CONF_NAME, entry.data.get(CONF_NAME, DEFAULT_NAME))
    device_id = entry.data[CONF_DEVICE_ID]
    manufacturer = entry.options.get(CONF_MANUFACTURER, entry.data.get(CONF_MANUFACTURER, DEFAULT_MANUFACTURER))
    model = entry.options.get(CONF_MODEL, entry.data.get(CONF_MODEL, DEFAULT_MODEL))

    entities = []
    for config in SENSORS_CONFIG:
        entities.append(TaylorBinarySensor(hass, device_name, device_id, manufacturer, model, entry.entry_id, config))
    
    async_add_entities(entities)


class TaylorBinarySensor(BinarySensorEntity):
    """Representation of a Taylor Grill Binary Sensor."""

    _attr_has_entity_name = True

    def __init__(self, hass, device_name, device_id, manufacturer, model, entry_id, config):
        self.hass = hass
        self._device_name = device_name
        self._device_id = device_id
        self._attr_name = config["name"]
        self._manufacturer = manufacturer
        self._model = model
        self._attr_unique_id = f"{entry_id}_{config['key']}"
        self._offset = config["offset"]
        self._attr_device_class = config["device_class"]
        self._attr_icon = config["icon"]
        self._is_on = False
        
        self._topic_state = f"{device_id}/dev2app"

    async def async_added_to_hass(self):
        """Subscribe to MQTT."""
        @callback
        def message_received(message):
            self._parse_packet(message.payload)

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

    def _parse_packet(self, payload):
        """Parse status packet for errors."""
        if len(payload) < 6 or payload[0] != 0xFA:
            return

        if b'\xFE\x0B' in payload:
            try:
                idx = payload.find(b'\xFE\x0B')
                # Check if we have enough data for this specific offset
                if idx != -1 and idx + self._offset < len(payload):
                    val = payload[idx + self._offset]
                    new_state = (val == 1)
                    
                    if self._is_on != new_state:
                        self._is_on = new_state
                        self.async_write_ha_state()
            except IndexError:
                pass

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on