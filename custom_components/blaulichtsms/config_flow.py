"""BlaulichtSMS config flow."""

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
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


class BlaulichtSMSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """BlaulichtSMS config flow."""

    VERSION = 1

    async def async_step_user(
        self, info: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start a reauth flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm new credentials for an existing entry."""
        return await self._async_step_update_credentials(
            self._get_reauth_entry(), "reauth_confirm", "reauth_successful", user_input
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user update credentials for an existing entry."""
        return await self._async_step_update_credentials(
            self._get_reconfigure_entry(),
            "reconfigure",
            "reconfigure_successful",
            user_input,
        )

    async def _async_step_update_credentials(
        self,
        entry: config_entries.ConfigEntry,
        step_id: str,
        abort_reason: str,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Validate and store new credentials for ``entry``.

        Shared by the reauth and reconfigure steps, which differ only in the
        step id and the abort reason. Updating the entry fires the update
        listener registered in ``async_setup_entry``, which reloads the
        integration - so no explicit reload is issued here.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _validate_credentials(
                self.hass,
                entry.data[CONF_CUSTOMER_ID],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            if not errors:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, **user_input}
                )
                return self.async_abort(reason=abort_reason)

        return self.async_show_form(
            step_id=step_id,
            data_schema=reauth_schema(entry.data),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options Flow for BlaulichtSMS."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=options_schema(defaults)
        )
