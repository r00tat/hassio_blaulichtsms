"""BlaulichtSMS coordinator."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, UTC

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .blaulichtsms import (
    BlaulichtSmsAuthenticationError,
    BlaulichtSmsController,
    BlaulichtSmsSessionInitException,
    _parse_alarm_datetime,
)
from .constants import (
    CONF_ALARM_DURATION,
    CONF_CUSTOMER_ID,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_INFOS,
    CONF_USERNAME,
    DEFAULT_ALARM_DURATION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SHOW_INFOS,
)
from .errors import CoordinatorError

_LOGGER = logging.getLogger(__name__)


class BlaulichtSMSCoordinator(DataUpdateCoordinator):
    """Coordinator for the BlaulichtSMS dashboard API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: BlaulichtSmsController,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        self.api: BlaulichtSmsController = api
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="BlaulichtSMS",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from the API and derive `is_active`."""
        try:
            async with asyncio.timeout(10):
                _LOGGER.debug("fetching last alarm")
                alarm = await self.api.get_last_alarm()
        except (BlaulichtSmsAuthenticationError, BlaulichtSmsSessionInitException) as err:
            raise ConfigEntryAuthFailed(
                f"Authentication with blaulichtSMS failed: {err}"
            ) from err
        except (TimeoutError, aiohttp.ClientError) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        return {
            "alarm": alarm,
            "is_active": self._is_alarm_active(alarm),
        }

    def _is_alarm_active(self, alarm: dict | None) -> bool:
        """Return True if the alarm is still within its activity window."""
        if not alarm:
            return False

        now = datetime.now(UTC)

        end_date_raw = alarm.get("endDate")
        if end_date_raw:
            end_date = _parse_alarm_datetime(end_date_raw)
            if end_date is not None:
                return now < end_date

        alarm_date = _parse_alarm_datetime(alarm.get("alarmDate"))
        if alarm_date is None:
            return False
        return now < alarm_date + self.api.alarm_duration

    @staticmethod
    async def async_create(
        hass: HomeAssistant, config: ConfigEntry
    ) -> BlaulichtSMSCoordinator:
        """Create the coordinator for this config entry and do the first refresh.

        The instance is stored in ``entry.runtime_data`` by ``async_setup_entry``;
        the platforms read it from there instead of calling this again.
        """
        if config.data.get(CONF_CUSTOMER_ID) is None:
            raise CoordinatorError("customer id is required")

        alarm_duration = config.options.get(
            CONF_ALARM_DURATION,
            config.data.get(CONF_ALARM_DURATION, DEFAULT_ALARM_DURATION),
        )
        show_infos = config.options.get(
            CONF_SHOW_INFOS,
            config.data.get(CONF_SHOW_INFOS, DEFAULT_SHOW_INFOS),
        )
        scan_interval = config.options.get(
            CONF_SCAN_INTERVAL,
            config.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        blaulichtsms = BlaulichtSmsController(
            config.data[CONF_CUSTOMER_ID],
            config.data[CONF_USERNAME],
            config.data[CONF_PASSWORD],
            alarm_duration,
            show_infos,
            session=async_get_clientsession(hass),
        )
        coordinator = BlaulichtSMSCoordinator(hass, config, blaulichtsms, scan_interval)

        await coordinator.async_config_entry_first_refresh()
        return coordinator


BlaulichtSMSConfigEntry = ConfigEntry[BlaulichtSMSCoordinator]
