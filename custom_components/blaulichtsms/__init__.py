"""Blaulicht SMS component."""
import logging

from .constants import DOMAIN, CONF_CUSTOMER_ID

_LOGGER = logging.getLogger(__name__)


# List of integration names (string) your integration depends upon.
DEPENDENCIES = []


async def async_setup(hass, config):
    """Set up blaulichtsms component."""
    _LOGGER.info("loading %s completed.", DOMAIN)
    return True


async def async_setup_entry(hass, entry):
    """Set up from a config entry."""
    _LOGGER.info("setup entry %s", entry.data[CONF_CUSTOMER_ID])
    # host = entry.data['host']
    # config = hass.data[DOMAIN].get(host)
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(
            entry.data, "sensor"
        )
    )
