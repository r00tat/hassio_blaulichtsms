"""Shared entity base for the BlaulichtSMS integration."""

from __future__ import annotations

from homeassistant.helpers.sensor import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .constants import DOMAIN, VERSION
from .coordinator import BlaulichtSMSCoordinator


class BlaulichtSMSBaseEntity(CoordinatorEntity):
    """Base entity exposing the shared BlaulichtSMS device info."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BlaulichtSMSCoordinator,
        *,
        context=None,
    ) -> None:
        """Store the coordinator and build the device info."""
        super().__init__(coordinator, context=context)
        customer_id = coordinator.api.customer_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, customer_id)},
            name="BLSMS",
            manufacturer="BlaulichtSMS",
            model="API",
            sw_version=VERSION,
        )
