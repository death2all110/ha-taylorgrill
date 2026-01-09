"""Config flow for Taylor Grill integration."""
from __future__ import annotations
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    DOMAIN, 
    CONF_DEVICE_ID, 
    DEFAULT_NAME, 
    CONF_POLL_INTERVAL, 
    DEFAULT_POLL_INTERVAL,
    CONF_TEMP_UNIT,
    DEFAULT_TEMP_UNIT
)

_LOGGER = logging.getLogger(__name__)

# The Schema
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=5)
        ),
        vol.Optional(CONF_TEMP_UNIT, default=DEFAULT_TEMP_UNIT): SelectSelector(
            SelectSelectorConfig(
                options=[UnitOfTemperature.FAHRENHEIT,UnitOfTemperature.CELSIUS],
                mode=SelectSelectorMode.LIST,
                multiple=False
            )
        ),
    }
)

class TaylorGrillConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Taylor Grill."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return TaylorGrillOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        # 1. Check for duplicates
        await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
        self._abort_if_unique_id_configured()

        # 2. Create the entry
        return self.async_create_entry(
            title=user_input[CONF_NAME], 
            data=user_input
        )
class TaylorGrillOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Taylor Grill."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Build schema using current values as defaults
        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=self._config_entry.options.get(
                        CONF_POLL_INTERVAL,
                        self._config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=5)),
                vol.Optional(
                    CONF_TEMP_UNIT,
                    default=self._config_entry.options.get(
                        CONF_TEMP_UNIT,
                        self._config_entry.data.get(CONF_TEMP_UNIT, DEFAULT_TEMP_UNIT),
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS],
                        mode=SelectSelectorMode.LIST,
                        multiple=False
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)