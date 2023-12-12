"""Blaulichtsms Binary Sensors."""
from homeassistant.helpers.sensor import DeviceInfo
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import device_registry as dr

# from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
)
from homeassistant.components.binary_sensor import BinarySensorEntity

from datetime import datetime, timedelta

from .constants import (
    DOMAIN,
    CONF_CUSTOMER_ID,
    CONF_ALARM_DURATION,
    DEFAULT_ALARM_DURATION,
    VERSION,
)
from .schema import BLAULICHTSMS_SCHEMA
from .coordinator import BlaulichtSMSCoordinator


import logging


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
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> bool:
    """Set up a config entry."""
    _LOGGER.info(
        "setup of blaulichtsms binary_sensor entry: %s",
        entry.data.get(CONF_CUSTOMER_ID),
    )
    setup_result = await setup_blaulichtsms(
        hass, entry, async_add_entities, discovery_info
    )
    _LOGGER.debug("setup result %s", setup_result)
    return setup_result


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> bool:
    """Set up platform."""
    # Code for setting up your platform inside of the event loop.
    return await setup_blaulichtsms(hass, config, async_add_entities, discovery_info)


async def setup_blaulichtsms(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> bool:
    """Set up blaulichtsms binary_sensors."""
    coordinator = await BlaulichtSMSCoordinator.get_coordinator(hass, config)

    entities = [
        BlaulichtSMSAlarmActiveSensor(
            coordinator,
            hass,
            config.data.get(CONF_ALARM_DURATION, DEFAULT_ALARM_DURATION),
        ),
    ]
    async_add_entities(entities)

    # create matching device
    # Inside a component
    if hasattr(config, "entry_id") and config.entry_id:
        device_registry = dr.async_get(hass)

        # does not work, config.entry_id is empty...
        device_registry.async_get_or_create(
            config_entry_id=config.entry_id,
            # suggested_area="Kitchen",
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, coordinator.api.customer_id)
            },
            name=f"BlaulichtSMS {coordinator.api.customer_id}",
            manufacturer="BlaulichtSMS",
            model="API",
            sw_version=VERSION,
        )

    return True


class BlaulichtSMSAlarmActiveSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary Sensor for an active alarm."""

    def __init__(
        self,
        coordinator: BlaulichtSMSCoordinator,
        hass: HomeAssistant,
        alarm_duration: int,
    ) -> None:
        """Create a binary sensor."""
        self._alarm_duration = alarm_duration
        super().__init__(coordinator, context="alarm-active")
        self.hass = hass
        self.coordinator = coordinator
        self.blaulichtsms = self.coordinator.api
        self._attr_name = "BlaulichtSMS Alarm Active"
        self._attr_unique_id = f"blsms-{self.blaulichtsms.customer_id}-alarm-active"
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
        """Parse state from coordinator."""
        new_value = self.coordinator.data.get("alarmDate")
        alarm_date = datetime.fromisoformat(new_value)
        self._attr_is_on = datetime.now(alarm_date.tzinfo) < alarm_date + timedelta(
            seconds=self._alarm_duration
        )

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
