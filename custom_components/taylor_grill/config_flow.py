"""Config flow for Taylor Grill integration."""
from __future__ import annotations
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN, 
    CONF_DEVICE_ID, 
    DEFAULT_NAME,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL
    )


_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=5)
        ),
    }
)

class TaylorGrillConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Taylor Grill."""

    VERSION = 1

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