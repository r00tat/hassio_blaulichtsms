from homeassistant.helpers.sensor import DeviceInfo
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import device_registry as dr
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
from homeassistant.components.binary_sensor import BinarySensorEntity

from datetime import datetime, timedelta
import aiohttp
import json

from .blaulichtsms import BlaulichtSmsController
from .constants import (DOMAIN, CONF_CUSTOMER_ID, CONF_USERNAME, CONF_PASSWORD, CONF_ALARM_DURATION,
                        CONF_SHOW_INFOS, DEFAULT_ALARM_DURATION, DEFAULT_SHOW_INFOS, VERSION,
                        CONF_TRACK_RECIPIENT)
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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback, discovery_info=None
) -> bool:
    """setup a config entry"""
    _LOGGER.info("setup of blaulichtsms entry: %s", entry.data.get(CONF_CUSTOMER_ID))
    setup_result = await setup_blaulichtsms(hass, entry, async_add_entities, discovery_info)
    _LOGGER.debug("setup result %s", setup_result)
    return setup_result


async def async_setup_platform(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback, discovery_info=None) -> bool:
    """Set up platform."""
    # Code for setting up your platform inside of the event loop.
    return await setup_blaulichtsms(hass, config, async_add_entities, discovery_info)


async def setup_blaulichtsms(hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback, discovery_info=None) -> bool:
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
    entities = [
        BlaulichtSMSEntity(coordinator, blaulichtsms, hass, attribute, config) for attribute in SENSOR_FIELDS
    ] + [
        BlaulichtSMSAlarmActiveSensor(coordinator, blaulichtsms, hass, config.data.get(CONF_ALARM_DURATION, DEFAULT_ALARM_DURATION)),

    ] + ([
        BlaulichtSMSEntity(coordinator, blaulichtsms, hass, CONF_TRACK_RECIPIENT, config)
    ] if config.data.get(CONF_TRACK_RECIPIENT) else [
    ])
    async_add_entities(
        entities
    )

    # create matching device
    # Inside a component
    if hasattr(config, 'entry_id') and config.entry_id:
        device_registry = dr.async_get(hass)

        # does not work, config.entry_id is empty...
        device_registry.async_get_or_create(
            config_entry_id=config.entry_id,
            # suggested_area="Kitchen",
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, blaulichtsms.customer_id)
            },
            name=f"BlaulichtSMS {blaulichtsms.customer_id}",
            manufacturer="BlaulichtSMS",
            model="API",
            sw_version=VERSION,
        )

    return True


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
                _LOGGER.debug("fetching last alarm")
                return await self.api.get_last_alarm()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")


class BlaulichtSMSEntity(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: BlaulichtSMSCoordinator, blaulichtsms: BlaulichtSmsController, hass: HomeAssistant, attribute: str, config: ConfigEntry) -> None:
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

        self._config = config

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
        _LOGGER.debug("coordinator update for %s: %s", self.attribute, new_value)
        if self.attribute == "recipients":
            self._attr_native_value = len(list(filter(lambda r: (r.get("participation") == 'yes'), new_value)))
        elif self._is_date:
            self._attr_native_value = datetime.fromisoformat(new_value)
        elif self.attribute == "alarmText":
            self._attr_native_value = f"{new_value}".replace("/", " / ")
        elif self.attribute == "alarmGroups":
            self._attr_native_value = ", ".join([g.get('groupName', '') for g in new_value])
            self._attr_extra_state_attributes = new_value
        elif self.attribute == CONF_TRACK_RECIPIENT:
            recipient_number: str = self._config.data.get(CONF_TRACK_RECIPIENT)
            recipients: list[dict] = self.coordinator.data.get("recipients")
            found_receipient = next(x for x in recipients if x.get('msisdn') == recipient_number)
            if not found_receipient:
                self._attr_native_value = "unknown"
            else:
                self._attr_native_value = found_receipient.get("participation", "unknown")

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
            name=f"BlaulichtSMS {self.blaulichtsms.customer_id}",
            manufacturer="BlaulichtSMS",
            model="API",
            sw_version=VERSION,
            # via_device=(DOMAIN, self.api.bridgeid),
        )


class BlaulichtSMSAlarmActiveSensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator: BlaulichtSMSCoordinator, blaulichtsms: BlaulichtSmsController, hass: HomeAssistant, alarm_duration: int) -> None:
        self._alarm_duration = alarm_duration
        super().__init__(coordinator, context="alarm-active")
        self.blaulichtsms = blaulichtsms
        self.hass = hass
        self.coordinator = coordinator
        self._attr_name = f"BlaulichtSMS Alarm Active"
        self._attr_unique_id = f"blsms-{blaulichtsms.customer_id}-alarm-active"
        self._attr_is_on = False

        if self.coordinator.data:
            self.update_state_from_coordinator()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            self.update_state_from_coordinator()
        self.async_write_ha_state()

    def update_state_from_coordinator(self):
        """parse state from coordinator"""
        new_value = self.coordinator.data.get("alarmDate")
        alarm_date = datetime.fromisoformat(new_value)
        self._attr_is_on = datetime.now(alarm_date.tzinfo) < alarm_date + timedelta(seconds=self._alarm_duration)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.blaulichtsms.customer_id)
            },
            name=f"BlaulichtSMS {self.blaulichtsms.customer_id}",
            manufacturer="BlaulichtSMS",
            model="API",
            sw_version=VERSION,
            # via_device=(DOMAIN, self.api.bridgeid),
        )
