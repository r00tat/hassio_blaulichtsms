import logging
import json

from homeassistant import config_entries
import voluptuous as vol

from .constants import DOMAIN, CONF_CUSTOMER_ID
from .schema import BLAULICHTSMS_SCHEMA

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up entry."""
    _LOGGER.info("async setup entry %s", json.dumps(config_entry))


class BlaulichtSMSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """BlaulichtSMS config flow."""
    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1

    async def async_step_customer(self, info):
        if info is not None:
            await self.async_set_unique_id(info[CONF_CUSTOMER_ID])
            self._abort_if_unique_id_configured()
            self.async_create_entry(title=f"BlaulichtSMS {info[CONF_CUSTOMER_ID]}", data=info)

        return self.async_show_form(
            step_id="customer", data_schema=vol.Schema(BLAULICHTSMS_SCHEMA)
        )
