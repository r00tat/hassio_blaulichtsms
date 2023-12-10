from homeassistant.helpers.sensor import DeviceInfo
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
# from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

from datetime import datetime
import aiohttp

from .blaulichtsms import BlaulichtSmsController
from .constants import (DOMAIN, CONF_CUSTOMER_ID, CONF_USERNAME, CONF_PASSWORD, CONF_ALARM_DURATION,
                        CONF_SHOW_INFOS, DEFAULT_ALARM_DURATION, DEFAULT_SHOW_INFOS)
from .schema import BLAULICHTSMS_SCHEMA


from datetime import timedelta
import logging

import async_timeout


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(BLAULICHTSMS_SCHEMA)

_LOGGER = logging.getLogger(__name__)


SENSOR_FIELDS = [
    "customerId",
    "customerName",
    "alarmId",
    # "scenarioId",
    # "indexNumber",
    "alarmGroups",
    "alarmDate",
    "endDate",
    "authorName",
    "alarmText",
    "audioUrl",
    "usersAlertedCount",
    # "geolocation",
    "coordinates",
    # "recipients",
]


async def async_setup_platform(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback, discovery_info=None):
    """Set up platform."""
    # Code for setting up your platform inside of the event loop.
    blaulichtsms = BlaulichtSmsController(
        config[CONF_CUSTOMER_ID],
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        config.get(CONF_ALARM_DURATION, DEFAULT_ALARM_DURATION),
        config.get(CONF_SHOW_INFOS, DEFAULT_SHOW_INFOS),
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
    async_add_entities(
        BlaulichtSMSEntity(coordinator, blaulichtsms, hass, attribute) for attribute in SENSOR_FIELDS
    )


class BlaulichtSMSCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass: HomeAssistant, api: BlaulichtSmsController):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="BlaulichtSMS",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self.api: BlaulichtSmsController = api

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
                _LOGGER.info("fetching last alarm")
                return await self.api.get_last_alarm()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")


class BlaulichtSMSEntity(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: BlaulichtSMSCoordinator, blaulichtsms: BlaulichtSmsController, hass: HomeAssistant, attribute: str) -> None:
        super().__init__(coordinator, context=attribute)
        self.blaulichtsms = blaulichtsms
        self.hass = hass
        self.coordinator = coordinator
        # self.device_class =
        # self.state_class = 'measurement'
        # self._attr_state_class = SensorStateClass.MEASUREMENT
        self.attribute = attribute
        self._attr_name = f"BlaulichtSMS {self.attribute}"
        self._attr_unique_id = f"blsms-{blaulichtsms.customer_id}-{self.attribute}"
        self._is_date = self.attribute.lower().endswith("date")
        if self._is_date:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

        if self.coordinator.data:
            self.update_state_from_coordinator()

    # async def async_update(self):
    #     """Retrieve latest state."""
    #     self._state = await self.blaulichtsms.get_alarms()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            self.update_state_from_coordinator()
        self.async_write_ha_state()

    def update_state_from_coordinator(self):
        """parse state from coordinator"""
        new_value = self.coordinator.data.get(self.attribute)
        _LOGGER.info("coordinator update for %s: %s", self.attribute, new_value)
        if self.attribute == "recipients":
            self._attr_native_value = len(list(filter(lambda r: (r.get("participation") == 'yes'), new_value)))
        elif self._is_date:
            self._attr_native_value = datetime.fromisoformat(new_value)
        elif self.attribute == "alarmText":
            self._attr_native_value = f"{new_value}".replace("/", " / ")
        else:
            self._attr_native_value = new_value
        if self.attribute == "alarmText":
            self.extract_extra_attributes()

    def extract_extra_attributes(self) -> None:
        """load the additional attributes from the alarm to the state"""
        extra_attributes = {}
        if self.coordinator.data:
            for key in SENSOR_FIELDS:
                extra_attributes[key] = self.coordinator.data.get(key)
            extra_attributes['latitude'] = self.coordinator.data.get('coordinates', {}).get('lat')
            extra_attributes['longitude'] = self.coordinator.data.get('coordinates', {}).get('lon')
        self._attr_extra_state_attributes = extra_attributes

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.blaulichtsms.customer_id)
            },
            name=self.name,
            manufacturer="BlaulichtSMS",
            model="API",
            sw_version="1.0.0",
            # via_device=(DOMAIN, self.api.bridgeid),
        )
