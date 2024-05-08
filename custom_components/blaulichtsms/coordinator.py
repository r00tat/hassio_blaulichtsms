"""BlaulichtSMS coordinator."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from datetime import timedelta
import aiohttp


from .blaulichtsms import BlaulichtSmsController
from .constants import (
    CONF_CUSTOMER_ID,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ALARM_DURATION,
    CONF_SHOW_INFOS,
    DEFAULT_ALARM_DURATION,
    DEFAULT_SHOW_INFOS,
)

from .errors import CoordinatorError


import logging

import async_timeout


_LOGGER = logging.getLogger(__name__)


class BlaulichtSMSCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    coordinators: dict[str, BlaulichtSMSCoordinator] = {}

    def __init__(self, hass: HomeAssistant, api: BlaulichtSmsController):
        """Initialize my coordinator."""
        self.api: BlaulichtSmsController = api
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="BlaulichtSMS",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                # Grab active context variables to limit data required to be fetched from API
                # Note: using context is not required if there is no need or ability to limit
                # data retrieved from API.
                # listening_idx = set(self.async_contexts())
                _LOGGER.debug("fetching last alarm")
                return await self.api.get_last_alarm()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    @staticmethod
    async def get_coordinator(hass: HomeAssistant, config: ConfigEntry):
        """Get coordinator factory."""
        if config.data.get(CONF_CUSTOMER_ID) is None:
            raise CoordinatorError("customer id is required")

        if not BlaulichtSMSCoordinator.coordinators.get(config.data[CONF_CUSTOMER_ID]):
            blaulichtsms = BlaulichtSmsController(
                config.data[CONF_CUSTOMER_ID],
                config.data[CONF_USERNAME],
                config.data[CONF_PASSWORD],
                config.data.get(CONF_ALARM_DURATION, DEFAULT_ALARM_DURATION),
                config.data.get(CONF_SHOW_INFOS, DEFAULT_SHOW_INFOS),
            )
            # Fetch initial data so we have data when entities subscribe
            #
            # If the refresh fails, async_config_entry_first_refresh will
            # raise ConfigEntryNotReady and setup will try again later
            #
            # If you do not want to retry setup on failure, use
            # coordinator.async_refresh() instead
            #
            coordinator = BlaulichtSMSCoordinator(hass, blaulichtsms)

            await coordinator.async_config_entry_first_refresh()
            BlaulichtSMSCoordinator.coordinators[CONF_CUSTOMER_ID] = coordinator
        return BlaulichtSMSCoordinator.coordinators[CONF_CUSTOMER_ID]
