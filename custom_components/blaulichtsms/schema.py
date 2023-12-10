import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .constants import (CONF_CUSTOMER_ID, CONF_USERNAME, CONF_PASSWORD, CONF_ALARM_DURATION,
                        CONF_SHOW_INFOS, DEFAULT_ALARM_DURATION, DEFAULT_SHOW_INFOS)

BLAULICHTSMS_SCHEMA = {
    vol.Required(CONF_CUSTOMER_ID, description="Customer ID"): cv.string,
    vol.Required(CONF_USERNAME, description="Username"): cv.string,
    vol.Required(CONF_PASSWORD, description="Password"): cv.string,
    vol.Optional(CONF_ALARM_DURATION, default=DEFAULT_ALARM_DURATION, description="Alarm duration to show as active (seconds)"): cv.positive_int,
    vol.Optional(CONF_SHOW_INFOS, default=DEFAULT_SHOW_INFOS, description="Display infos as alarm"): cv.boolean,
}
