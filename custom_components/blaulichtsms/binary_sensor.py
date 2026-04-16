"""Blaulichtsms Binary Sensors."""

import logging
from datetime import datetime, timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sensor import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .constants import (
    CONF_CUSTOMER_ID,
    CONF_NEW_ALARM_DURATION,
    CONF_TRACK_RECIPIENT,
    DEFAULT_NEW_ALARM_DURATION,
    DOMAIN,
    VERSION,
)
from .coordinator import BlaulichtSMSCoordinator
from .schema import BLAULICHTSMS_SCHEMA

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(BLAULICHTSMS_SCHEMA)

_LOGGER = logging.getLogger(__name__)


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
    return await setup_blaulichtsms(hass, entry, async_add_entities, discovery_info)


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
    """Set up blaulichtsms binary sensors."""
    coordinator = await BlaulichtSMSCoordinator.get_coordinator(hass, config)

    new_alarm_duration = config.options.get(
        CONF_NEW_ALARM_DURATION,
        config.data.get(CONF_NEW_ALARM_DURATION, DEFAULT_NEW_ALARM_DURATION),
    )
    track_recipient = config.options.get(
        CONF_TRACK_RECIPIENT, config.data.get(CONF_TRACK_RECIPIENT)
    )

    entities = [
        BlaulichtSMSAlarmActiveSensor(coordinator),
        BlaulichtSMSNewAlarmActiveSensor(
            coordinator, new_alarm_duration, track_recipient or None
        ),
        BlaulichtSMSNewAlarmActiveSensor(
            coordinator,
            hass,
            config.data.get(CONF_NEW_ALARM_DURATION, DEFAULT_NEW_ALARM_DURATION),
            config.data.get(CONF_TRACK_RECIPIENT),
        ),
    ]
    async_add_entities(entities)
    return True


class _BlaulichtSMSBinarySensorBase(CoordinatorEntity, BinarySensorEntity):
    """Shared device info for all blaulichtSMS binary sensors."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        customer_id = self.coordinator.api.customer_id
        return DeviceInfo(
            identifiers={(DOMAIN, customer_id)},
            name=f"BlaulichtSMS {customer_id}",
            manufacturer="BlaulichtSMS",
            model="API",
            sw_version=VERSION,
        )


class BlaulichtSMSAlarmActiveSensor(_BlaulichtSMSBinarySensorBase):
    """Binary sensor indicating whether the last alarm is still active."""

    def __init__(self, coordinator: BlaulichtSMSCoordinator) -> None:
        """Create the sensor."""
        super().__init__(coordinator, context="alarm-active")
        customer_id = coordinator.api.customer_id
        self._attr_name = "BlaulichtSMS Alarm Active"
        self._attr_unique_id = f"blsms-{customer_id}-alarm-active"
        self._attr_is_on = self._derive_is_on()

    def _derive_is_on(self) -> bool:
        data = self.coordinator.data
        return bool(data and data.get("is_active"))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self._derive_is_on()
        self.async_write_ha_state()


class BlaulichtSMSNewAlarmActiveSensor(_BlaulichtSMSBinarySensorBase):
    """Binary sensor that fires False→True when a fresh alarm arrives."""

    def __init__(
        self,
        coordinator: BlaulichtSMSCoordinator,
        new_alarm_duration: int,
        track_recipient: str | None,
    ) -> None:
        """Create the sensor."""
        super().__init__(coordinator, context="new-alarm-active")
        customer_id = coordinator.api.customer_id
        self._new_alarm_duration = new_alarm_duration
        self._track_recipient = track_recipient or None
        self._last_alarm_id = None
        self._attr_name = "BlaulichtSMS New Alarm Active"
        self._attr_unique_id = f"blsms-{customer_id}-new-alarm-active"
        self._attr_is_on = False

    def _alarm(self) -> dict | None:
        data = self.coordinator.data
        if not data:
            return None
        return data.get("alarm")

    @callback
    def _handle_coordinator_update(self) -> None:
        """React to a new coordinator poll."""
        alarm = self._alarm()
        if not alarm:
            if self._attr_is_on:
                self._attr_is_on = False
                self.async_write_ha_state()
            return

        alarm_id = alarm.get("alarmId")
        if alarm_id != self._last_alarm_id:
            self._last_alarm_id = alarm_id
            self._attr_is_on = False
            self.async_write_ha_state()

        target = self._evaluate_target(alarm)
        if self._attr_is_on != target:
            self._attr_is_on = target
            self.async_write_ha_state()

    def _evaluate_target(self, alarm: dict) -> bool:
        """Return the intended is_on value for the given alarm payload."""
        alarm_date_raw = alarm.get("alarmDate")
        if not alarm_date_raw:
            return False
        alarm_date = datetime.fromisoformat(alarm_date_raw)
        within_window = datetime.now(alarm_date.tzinfo) < alarm_date + timedelta(
            seconds=self._new_alarm_duration
        )
        if not within_window:
            return False

        if self._track_recipient:
            recipient = next(
                (
                    r
                    for r in alarm.get("recipients", [])
                    if r.get("msisdn") == self._track_recipient
                ),
                None,
            )
            return bool(recipient and recipient.get("participation") == "yes")
        return True
