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
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sensor import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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


def count_by_participation(recipients: list[dict] | None) -> dict[str, int]:
    """Count recipients by participation status.

    Returns a dict with keys yes/no/pending/total. Unknown statuses are counted
    only in total, so yes+no+pending <= total.
    """
    counts = {"yes": 0, "no": 0, "pending": 0, "total": 0}
    for r in recipients or []:
        counts["total"] += 1
        status = r.get("participation")
        if status in counts:
            counts[status] += 1
    return counts


def confirmed_by_function(recipients: list[dict] | None) -> list[dict]:
    """Aggregate recipients per function, keeping only functions actually seen.

    Returned list is sorted by each function's `order` field. Each entry carries
    the function metadata (id, name, shortForm, colors) plus yes/no/pending/total
    counts of recipients holding that function.
    """
    buckets: dict[str, dict] = {}
    for recipient in recipients or []:
        status = recipient.get("participation")
        for fn in recipient.get("functions") or []:
            fn_id = fn.get("functionId")
            if fn_id is None:
                continue
            entry = buckets.get(fn_id)
            if entry is None:
                entry = {
                    "functionId": fn_id,
                    "name": fn.get("name"),
                    "shortForm": fn.get("shortForm"),
                    "order": fn.get("order", 0),
                    "backgroundColor": fn.get("backgroundHexColorCode"),
                    "foregroundColor": fn.get("foregroundHexColorCode"),
                    "yes": 0,
                    "no": 0,
                    "pending": 0,
                    "total": 0,
                }
                buckets[fn_id] = entry
            entry["total"] += 1
            if status in ("yes", "no", "pending"):
                entry[status] += 1
    return sorted(buckets.values(), key=lambda e: (e["order"], e["shortForm"] or ""))


def get_address(alarm: dict | None) -> str | None:
    """Return the street address from alarm.geolocation.address, or None."""
    if not alarm:
        return None
    geo = alarm.get("geolocation") or {}
    return geo.get("address")


SENSOR_FIELDS = [
    "customerId",
    "customerName",
    "alarmId",
    "alarmGroups",
    "alarmDate",
    "endDate",
    "authorName",
    "alarmText",
    "audioUrl",
    "usersAlertedCount",
    "coordinates",
]

RECIPIENT_COUNT_FIELDS = [
    "recipients_yes",
    "recipients_no",
    "recipients_pending",
    "recipients_total",
]

DERIVED_FIELDS = [
    "confirmed_by_function",
    "address",
]

SENSOR_ICONS = {
    "customerId": "mdi:identifier",
    "customerName": "mdi:domain",
    "alarmId": "mdi:pound",
    "alarmGroups": "mdi:account-group",
    "alarmDate": "mdi:clock-start",
    "endDate": "mdi:clock-end",
    "authorName": "mdi:account-edit",
    "alarmText": "mdi:message-alert",
    "audioUrl": "mdi:volume-high",
    "usersAlertedCount": "mdi:account-multiple",
    "coordinates": "mdi:map-marker",
    "recipients_yes": "mdi:account-check",
    "recipients_no": "mdi:account-cancel",
    "recipients_pending": "mdi:account-clock",
    "recipients_total": "mdi:account-multiple",
    "confirmed_by_function": "mdi:badge-account-horizontal",
    "address": "mdi:map-marker",
    CONF_TRACK_RECIPIENT: "mdi:cellphone-check",
}

SENSOR_NAMES = {
    "customerId": "Kunden-ID",
    "customerName": "Kunde",
    "alarmId": "Alarm-ID",
    "alarmGroups": "Alarmgruppen",
    "alarmDate": "Alarmzeit",
    "endDate": "Endzeit",
    "authorName": "Verfasser",
    "alarmText": "Alarmtext",
    "audioUrl": "Audio-URL",
    "usersAlertedCount": "Alarmierte Nutzer",
    "coordinates": "Koordinaten",
    "recipients_yes": "Empfänger Zusage",
    "recipients_no": "Empfänger Absage",
    "recipients_pending": "Empfänger Ausstehend",
    "recipients_total": "Empfänger Gesamt",
    "confirmed_by_function": "Zusagen nach Funktion",
    "address": "Adresse",
    CONF_TRACK_RECIPIENT: "Verfolgter Empfänger",
}


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
    return await setup_blaulichtsms(hass, config, async_add_entities, discovery_info)


async def setup_blaulichtsms(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> bool:
    """Set up blaulichtsms sensors."""
    coordinator = await BlaulichtSMSCoordinator.get_coordinator(hass, config)

    try:
        await coordinator.async_refresh()
    except Exception as ex:
        _LOGGER.exception("BlaulichtSMS failed to start")
        raise PlatformNotReady(
            f"Failed to connect to Blaulicht SMS {config.data.get(CONF_CUSTOMER_ID)}: {ex}"
        ) from ex

    entities = [
        BlaulichtSMSEntity(coordinator, attribute, config)
        for attribute in SENSOR_FIELDS + RECIPIENT_COUNT_FIELDS + DERIVED_FIELDS
    ]
    if config.data.get(CONF_TRACK_RECIPIENT):
        entities.append(BlaulichtSMSEntity(coordinator, CONF_TRACK_RECIPIENT, config))

    async_add_entities(entities)
    return True


class BlaulichtSMSEntity(CoordinatorEntity, SensorEntity):
    """Blaulichtsms generic sensor entity."""

    def __init__(
        self,
        coordinator: BlaulichtSMSCoordinator,
        attribute: str,
        config: ConfigEntry,
    ) -> None:
        """Create a BlaulichtSMSEntity."""
        super().__init__(coordinator, context=attribute)
        self.blaulichtsms = coordinator.api
        self.attribute = attribute
        friendly = SENSOR_NAMES.get(self.attribute, self.attribute)
        self._attr_name = f"BlaulichtSMS {friendly}"
        self._attr_unique_id = f"blsms-{self.blaulichtsms.customer_id}-{self.attribute}"
        self._is_date = self.attribute.lower().endswith("date")
        if self._is_date:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

        icon = SENSOR_ICONS.get(self.attribute)
        if icon:
            self._attr_icon = icon

        self._config = config

        if self._current_alarm():
            self.update_state_from_coordinator()

    def _current_alarm(self) -> dict | None:
        """Return the alarm dict from coordinator data, or None."""
        data = self.coordinator.data
        if not data:
            return None
        return data.get("alarm")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._current_alarm():
            self.update_state_from_coordinator()
        else:
            self._attr_native_value = None
            self._attr_extra_state_attributes = None
        self.async_write_ha_state()

    def update_state_from_coordinator(self) -> None:
        """Parse state from coordinator."""
        alarm = self._current_alarm()
        if alarm is None:
            return

        new_value = alarm.get(self.attribute)
        _LOGGER.debug("coordinator update for %s: %s", self.attribute, new_value)

        if self.attribute.startswith("recipients_"):
            key = self.attribute.removeprefix("recipients_")
            self._attr_native_value = count_by_participation(
                alarm.get("recipients")
            )[key]
            return

        if self.attribute == "confirmed_by_function":
            functions = confirmed_by_function(alarm.get("recipients"))
            self._attr_native_value = len(functions)
            self._attr_extra_state_attributes = {"functions": functions}
            return

        if self.attribute == "address":
            self._attr_native_value = get_address(alarm)
            return

        if self._is_date:
            self._attr_native_value = (
                datetime.fromisoformat(new_value) if new_value else None
            )
        elif self.attribute == "alarmText":
            self._attr_native_value = f"{new_value}".replace("/", " / ")
        elif self.attribute == "alarmGroups":
            self._attr_native_value = ", ".join(
                [g.get("groupName", "") for g in (new_value or [])]
            )
            self._attr_extra_state_attributes = new_value
        elif self.attribute == CONF_TRACK_RECIPIENT:
            recipient_number: str = self._config.data.get(CONF_TRACK_RECIPIENT)
            recipients: list[dict] = alarm.get("recipients") or []
            found_recipient = next(
                (x for x in recipients if x.get("msisdn") == recipient_number),
                None,
            )
            if not found_recipient:
                self._attr_native_value = "unknown"
            else:
                self._attr_native_value = found_recipient.get(
                    "participation", "unknown"
                )
        else:
            self._attr_native_value = new_value

        if self.attribute == "alarmText":
            self.extract_extra_attributes()

    def extract_extra_attributes(self) -> None:
        """Load additional attributes from the alarm to the state."""
        alarm = self._current_alarm()
        if alarm is None:
            return

        extra_attributes = {key: alarm.get(key) for key in SENSOR_FIELDS}
        coordinates = alarm.get("coordinates") or {}
        extra_attributes["latitude"] = coordinates.get("lat")
        extra_attributes["longitude"] = coordinates.get("lon")
        self._attr_extra_state_attributes = extra_attributes

    @property
    def suggested_object_id(self) -> str:
        """Preserve the pre-rename entity_id for fresh installations."""
        return f"blaulichtsms_{self.attribute.lower()}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.blaulichtsms.customer_id)},
            name=f"BlaulichtSMS {self.blaulichtsms.customer_id}",
            manufacturer="BlaulichtSMS",
            model="API",
            sw_version=VERSION,
        )
