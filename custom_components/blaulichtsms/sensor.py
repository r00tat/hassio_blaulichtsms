"""blaulichtsms sensors."""
import logging
from datetime import datetime

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sensor import DeviceInfo

# from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .constants import (
    CONF_CUSTOMER_ID,
    CONF_TRACK_RECIPIENT,
    DOMAIN,
    VERSION,
)
from .coordinator import BlaulichtSMSCoordinator
from .schema import BLAULICHTSMS_SCHEMA

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
    _LOGGER.info("setup of blaulichtsms entry: %s", entry.data.get(CONF_CUSTOMER_ID))
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
    """Set up blaulichtsms."""
    coordinator = await BlaulichtSMSCoordinator.get_coordinator(hass, config)

    entities = [
        BlaulichtSMSEntity(coordinator, hass, attribute, config)
        for attribute in SENSOR_FIELDS
    ] + (
        [BlaulichtSMSEntity(coordinator, hass, CONF_TRACK_RECIPIENT, config)]
        if config.data.get(CONF_TRACK_RECIPIENT)
        else []
    )
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


class BlaulichtSMSEntity(CoordinatorEntity, SensorEntity):
    """Blaulichtsms generic entity."""

    def __init__(
        self,
        coordinator: BlaulichtSMSCoordinator,
        hass: HomeAssistant,
        attribute: str,
        config: ConfigEntry,
    ) -> None:
        """Create a BlaulichtSMSEnitity."""
        super().__init__(coordinator, context=attribute)
        self.hass = hass
        self.coordinator = coordinator
        self.blaulichtsms = self.coordinator.api
        # self.device_class =
        # self.state_class = 'measurement'
        # self._attr_state_class = SensorStateClass.MEASUREMENT
        self.attribute = attribute
        self._attr_name = f"BlaulichtSMS {self.attribute}"
        self._attr_unique_id = f"blsms-{self.blaulichtsms.customer_id}-{self.attribute}"
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
        """Parse state from coordinator."""
        new_value = self.coordinator.data.get(self.attribute)
        _LOGGER.debug("coordinator update for %s: %s", self.attribute, new_value)
        if self.attribute == "recipients":
            self._attr_native_value = len(
                list(filter(lambda r: (r.get("participation") == "yes"), new_value))
            )
        elif self._is_date:
            self._attr_native_value = datetime.fromisoformat(new_value)
        elif self.attribute == "alarmText":
            self._attr_native_value = f"{new_value}".replace("/", " / ")
        elif self.attribute == "alarmGroups":
            self._attr_native_value = ", ".join(
                [g.get("groupName", "") for g in new_value]
            )
            self._attr_extra_state_attributes = new_value
        elif self.attribute == CONF_TRACK_RECIPIENT:
            recipient_number: str = self._config.data.get(CONF_TRACK_RECIPIENT)
            recipients: list[dict] = self.coordinator.data.get("recipients")
            found_receipient = next(
                x for x in recipients if x.get("msisdn") == recipient_number
            )
            if not found_receipient:
                self._attr_native_value = "unknown"
            else:
                self._attr_native_value = found_receipient.get(
                    "participation", "unknown"
                )

        else:
            self._attr_native_value = new_value
        if self.attribute == "alarmText":
            self.extract_extra_attributes()

    def extract_extra_attributes(self) -> None:
        """Load the additional attributes from the alarm to the state."""
        extra_attributes = {}
        if self.coordinator.data:
            for key in SENSOR_FIELDS:
                extra_attributes[key] = self.coordinator.data.get(key)
            extra_attributes["latitude"] = self.coordinator.data.get(
                "coordinates", {}
            ).get("lat")
            extra_attributes["longitude"] = self.coordinator.data.get(
                "coordinates", {}
            ).get("lon")
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
