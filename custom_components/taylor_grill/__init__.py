"""The Taylor Grill integration."""
from __future__ import annotations

import importlib
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# Add SENSOR and SWITCH to the list of platforms
PLATFORMS: list[Platform] = [
    Platform.CLIMATE, 
    Platform.SENSOR, 
    Platform.SWITCH, 
    Platform.BINARY_SENSOR
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Taylor Grill from a config entry."""
    
    # Pre-import platforms in a background thread to avoid blocking the event loop.
    # This fixes the "Detected blocking call to import_module" error.
    await hass.async_add_executor_job(ensure_platforms_imported)

    # Forward the setup to all platforms (Climate, Sensor, Switch)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True

def ensure_platforms_imported():
    """Import platforms in executor to cache them in sys.modules."""
    for platform in PLATFORMS:
        importlib.import_module(f".{platform}", __package__)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)