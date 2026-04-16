"""BlaulichtSMS config flow."""

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .blaulichtsms import BlaulichtSmsController, BlaulichtSmsSessionInitException
from .constants import CONF_CUSTOMER_ID, CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .schema import BLAULICHTSMS_SCHEMA, options_schema, reauth_schema

_LOGGER = logging.getLogger(__name__)


async def _validate_credentials(
    hass, customer_id: str, username: str, password: str
) -> dict[str, str]:
    """Return a dict of errors (empty on success)."""
    session = async_get_clientsession(hass)
    blsms = BlaulichtSmsController(customer_id, username, password, session=session)
    try:
        await blsms.get_session()
    except BlaulichtSmsSessionInitException:
        _LOGGER.exception("blaulichtsms authentication failed")
        return {"base": "auth"}
    except aiohttp.ClientError:
        _LOGGER.exception("failed to connect to blaulichtsms")
        return {"base": "cannot_connect"}
    return {}


@config_entries.HANDLERS.register(DOMAIN)
class BlaulichtSMSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """BlaulichtSMS config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, info: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Get initial step for Config Flow."""
        _LOGGER.debug(
            "%s step user started for customer %s",
            DOMAIN,
            info.get(CONF_CUSTOMER_ID) if info else None,
        )

        errors: dict[str, str] = {}
        if info is not None:
            await self.async_set_unique_id(info[CONF_CUSTOMER_ID])
            self._abort_if_unique_id_configured()

            errors = await _validate_credentials(
                self.hass,
                info[CONF_CUSTOMER_ID],
                info[CONF_USERNAME],
                info[CONF_PASSWORD],
            )
            if not errors:
                return self.async_create_entry(
                    title=f"BlaulichtSMS {info[CONF_CUSTOMER_ID]}", data=info
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(BLAULICHTSMS_SCHEMA),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> data_entry_flow.FlowResult:
        """Start a reauth flow."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Confirm new credentials for an existing entry."""
        assert self._reauth_entry is not None

        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _validate_credentials(
                self.hass,
                self._reauth_entry.data[CONF_CUSTOMER_ID],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={**self._reauth_entry.data, **user_input},
                )
                await self.hass.config_entries.async_reload(
                    self._reauth_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=reauth_schema(self._reauth_entry.data),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow."""
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
            return self.async_create_entry(title="", data=user_input)

        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=options_schema(defaults)
        )
