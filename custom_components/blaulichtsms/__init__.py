"""Blaulicht SMS component."""
import logging

from .constants import DOMAIN, CONF_CUSTOMER_ID
from homeassistant.core import callback, HomeAssistant
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


# List of integration names (string) your integration depends upon.
DEPENDENCIES = []


async def async_setup(hass: HomeAssistant, config: ConfigEntry):
    """Set up blaulichtsms component."""
    _LOGGER.info("loading %s completed.", DOMAIN)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up from a config entry."""
    _LOGGER.info("setup entry %s", entry.data[CONF_CUSTOMER_ID])
    # host = entry.data['host']
    # config = hass.data[DOMAIN].get(host)
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(
            entry, "sensor"
        )
    )
    return True
