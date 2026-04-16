"""BlaulichtSMS schemas."""

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from .constants import (
    CONF_ALARM_DURATION,
    CONF_CUSTOMER_ID,
    CONF_NEW_ALARM_DURATION,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_INFOS,
    CONF_TRACK_RECIPIENT,
    CONF_USERNAME,
    DEFAULT_ALARM_DURATION,
    DEFAULT_NEW_ALARM_DURATION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SHOW_INFOS,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

BLAULICHTSMS_SCHEMA = {
    vol.Required(CONF_CUSTOMER_ID): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(
        CONF_ALARM_DURATION, default=DEFAULT_ALARM_DURATION
    ): cv.positive_int,
    vol.Optional(CONF_SHOW_INFOS, default=DEFAULT_SHOW_INFOS): cv.boolean,
    vol.Optional(
        CONF_NEW_ALARM_DURATION, default=DEFAULT_NEW_ALARM_DURATION
    ): cv.positive_int,
    vol.Optional(CONF_TRACK_RECIPIENT): cv.string,
    vol.Optional(
        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
    ): vol.All(cv.positive_int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
}


def options_schema(data: dict) -> vol.Schema:
    """Create an options schema for OptionsFlow."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_ALARM_DURATION,
                default=data.get(CONF_ALARM_DURATION, DEFAULT_ALARM_DURATION),
            ): cv.positive_int,
            vol.Optional(
                CONF_SHOW_INFOS,
                default=data.get(CONF_SHOW_INFOS, DEFAULT_SHOW_INFOS),
            ): cv.boolean,
            vol.Optional(
                CONF_NEW_ALARM_DURATION,
                default=data.get(
                    CONF_NEW_ALARM_DURATION, DEFAULT_NEW_ALARM_DURATION
                ),
            ): cv.positive_int,
            vol.Optional(
                CONF_TRACK_RECIPIENT,
                default=data.get(CONF_TRACK_RECIPIENT, ""),
            ): cv.string,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(
                cv.positive_int,
                vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
            ),
        }
    )


def reauth_schema(data: dict) -> vol.Schema:
    """Create a schema for the reauth flow (username + password only)."""
    return vol.Schema(
        {
            vol.Required(
                CONF_USERNAME, default=data.get(CONF_USERNAME, "")
            ): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
        }
    )
