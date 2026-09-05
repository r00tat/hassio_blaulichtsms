"""Blaulicht SMS component."""

import logging

from homeassistant.core import HomeAssistant

from .constants import CONF_CUSTOMER_ID, PLATFORMS
from .coordinator import BlaulichtSMSConfigEntry, BlaulichtSMSCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: BlaulichtSMSConfigEntry
) -> bool:
    """Set up from a config entry."""
    customer_id = entry.data[CONF_CUSTOMER_ID]
    _LOGGER.info("setup entry %s", customer_id)

    entry.runtime_data = await BlaulichtSMSCoordinator.async_create(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BlaulichtSMSConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: BlaulichtSMSConfigEntry
) -> None:
    """Reload the integration when data or options change."""
    await hass.config_entries.async_reload(entry.entry_id)
