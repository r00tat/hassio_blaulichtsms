"""BlaulichtSMS constants."""

import json
from pathlib import Path

DOMAIN = "blaulichtsms"

CONF_CUSTOMER_ID = "customer_id"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_ALARM_DURATION = "alarm_duration"
CONF_SHOW_INFOS = "show_infos"
CONF_TRACK_RECIPIENT = "track_recipient"
CONF_NEW_ALARM_DURATION = "new_alarm_duration"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_ALARM_DURATION = 3600
DEFAULT_SHOW_INFOS = False
DEFAULT_NEW_ALARM_DURATION = 300
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 3600

PLATFORMS = ["sensor", "binary_sensor"]

VERSION = json.loads((Path(__file__).parent / "manifest.json").read_text())["version"]
