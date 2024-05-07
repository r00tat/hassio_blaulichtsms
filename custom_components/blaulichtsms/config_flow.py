"""BlaulichtSMS config flow."""

import aiohttp
import logging
import json
from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback, HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant import data_entry_flow
from homeassistant.helpers.entity_platform import AddEntitiesCallback

import voluptuous as vol

from .constants import DOMAIN, CONF_CUSTOMER_ID, CONF_USERNAME, CONF_PASSWORD
from .schema import BLAULICHTSMS_SCHEMA, options_schema
from .blaulichtsms import BlaulichtSmsController

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
):
    """Set up entry."""
    _LOGGER.debug("async setup entry %s", config_entry.data.get(CONF_CUSTOMER_ID))


@config_entries.HANDLERS.register(DOMAIN)
class BlaulichtSMSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """BlaulichtSMS config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1

    async def async_step_user(self, info: dict[str, Any] = None):
        """Get Initial step for Config Flow."""
        self.hass.data.setdefault(DOMAIN, {})
        _LOGGER.debug("%s step user started, info: %s", DOMAIN, json.dumps(info))
        if info is not None:
            await self.async_set_unique_id(info[CONF_CUSTOMER_ID])
            self._abort_if_unique_id_configured()
            try:
                blsms = BlaulichtSmsController(
                    info[CONF_CUSTOMER_ID], info[CONF_USERNAME], info[CONF_PASSWORD]
                )
                alarm = await blsms.get_last_alarm()
                _LOGGER.info(
                    "Connected to blaulichtsms with %s and %s",
                    info[CONF_CUSTOMER_ID],
                    info[CONF_USERNAME],
                )
                _LOGGER.info("Last alarm: %s", alarm)
            except aiohttp.ClientError as e:
                _LOGGER.exception("failed to setup blaulichtsms: %s", e)
                return self.async_abort(reason="blsms_auth_failed")

            return self.async_create_entry(
                title=f"BlaulichtSMS {info[CONF_CUSTOMER_ID]}", data=info
            )

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(BLAULICHTSMS_SCHEMA)
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow."""
        _LOGGER.debug("get options flow")
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options Flow for BlaulichtSMS."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Manage the options."""
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.config_entry.data | user_input
            )
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="init", data_schema=options_schema(self.config_entry.data)
        )
