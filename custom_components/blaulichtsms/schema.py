import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .constants import (CONF_CUSTOMER_ID, CONF_USERNAME, CONF_PASSWORD, CONF_ALARM_DURATION,
                        CONF_SHOW_INFOS, DEFAULT_ALARM_DURATION, DEFAULT_SHOW_INFOS)

BLAULICHTSMS_SCHEMA = {
    vol.Required(CONF_CUSTOMER_ID): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_ALARM_DURATION, default=DEFAULT_ALARM_DURATION): cv.positive_int,
    vol.Optional(CONF_SHOW_INFOS, default=DEFAULT_SHOW_INFOS): cv.boolean,
}
