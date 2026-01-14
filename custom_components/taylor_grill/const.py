"""Constants for the Taylor Grill integration."""

from homeassistant.const import UnitOfTemperature

DOMAIN = "taylor_grill"
CONF_DEVICE_ID = "device_id"
CONF_TEMP_UNIT = "temp_unit"
CONF_NAME = "device_name"

CONF_MANUFACTURER = "manufacturer"
CONF_MODEL = "model"

DEFAULT_NAME = "Taylor Grill Smoker"
DEFAULT_TEMP_UNIT = UnitOfTemperature.FAHRENHEIT
DEFAULT_MANUFACTURER = "Taylor"
DEFAULT_MODEL="SmartSmoker"