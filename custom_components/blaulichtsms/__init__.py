"""Blaulicht SMS component."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .constants import CONF_CUSTOMER_ID, DOMAIN, PLATFORMS, VERSION
from .coordinator import BlaulichtSMSCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up blaulichtsms component."""
    _LOGGER.info("loading %s completed.", DOMAIN)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    customer_id = entry.data[CONF_CUSTOMER_ID]
    _LOGGER.info("setup entry %s", customer_id)

    coordinator = await BlaulichtSMSCoordinator.get_coordinator(hass, entry)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, coordinator.api.customer_id)},
        name=f"BlaulichtSMS {coordinator.api.customer_id}",
        manufacturer="BlaulichtSMS",
        model="API",
        sw_version=VERSION,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        BlaulichtSMSCoordinator.coordinators.pop(entry.data[CONF_CUSTOMER_ID], None)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
