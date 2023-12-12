"""BlaulichtSMS API."""
import logging
from datetime import datetime, timedelta
from pprint import pformat

import aiohttp


class BlaulichtSmsSessionInitException(Exception):
    """Exception for Session Init."""

    pass


# base source from https://github.com/stg93/blaulichtsms_einsatzmonitor_tv_controller
# modified for asnycio
class BlaulichtSmsController:
    """Handles the communication with `blaulichtSMS Dashboard API<https://github.com/blaulichtSMS/docs/blob/master/dashboard_api_v1.md>`_."""

    def __init__(
        self,
        customer_id,
        username,
        password,
        alarm_duration=3600,
        show_infos=False,
        base_url="https://api.blaulichtsms.net/blaulicht/api/alarm/v1/dashboard/",
    ):
        """Create new controller."""
        self.logger = logging.getLogger(__name__)

        self.customer_id = customer_id
        self.username = username
        self.password = password
        self.alarm_duration = timedelta(seconds=alarm_duration)
        self.show_infos = show_infos
        self.base_url = base_url

        self._session_token = None

    async def get_session(self):
        """Get a new session token from the blaulichtSMS Dashboard API at every call.

        :return: The session token
        """
        try:
            self.logger.debug("Initializing blaulichtSMS session...")
            content = {
                "customerId": self.customer_id,
                "username": self.username,
                "password": self.password,
            }

            async with aiohttp.ClientSession() as session, session.post(
                f"{self.base_url}login", json=content
            ) as r:
                json_body = await r.json()
                session_id = json_body["sessionId"]
                # response = requests.post(self.base_url + "login", json=content)
                # session_id = response.json()["sessionId"]
                if session_id:
                    self.logger.debug("Successfully initialized blaulichtSMS session")
                else:
                    self.logger.warning("Failed to initialize blaulichtSMS session")
                return session_id
        except aiohttp.ClientError() as e:
            self.logger.error("http request failed %s", e)
            raise e

    async def get_alarms(self) -> list[dict]:
        """Get the alarms from the blaulichtSMS Dashboard API."""
        if not self._session_token:
            self._session_token = await self.get_session()

        try:
            self.logger.debug("Requesting blaulichtSMS alarms...")
            async with aiohttp.ClientSession() as session, session.get(
                self.base_url + self._session_token
            ) as resp:
                # response = requests.get(self.base_url + self._session_token)
                self.logger.debug("Request successful")
                response_json = await resp.json()
                self.logger.debug("Response body: \n" + pformat(response_json))
                alarms = response_json.get("alarms", [])
                if self.show_infos:
                    alarms += response_json.get("infos", [])
                return alarms
        except aiohttp.ClientError as e:
            self.logger.error(
                "Failed to request blaulichtSMS alarms. Maybe there is no internet connection. %s",
                e,
            )
            return None

    async def get_last_alarm(self):
        """Get the last alarm."""
        alarms = await self.get_alarms()
        if len(alarms) == 0:
            return None
        alarms.sort(key=lambda a: a.get("alarmDate"))
        alarms.reverse()
        return alarms[0]

    async def get_anonymized_alarms(self):
        """Remove PII from the alarm."""
        alarms = await self.get_alarms()
        for a in alarms:
            a["recipients"] = len(
                list(
                    filter(lambda r: (r.get("participation") == "yes"), a["recipients"])
                )
            )
            del a["pointsOfInterest"]
        return alarms

    async def is_alarm(self):
        """Check if there is any active alarm.

        An alarm is active if it's datetime is greater than or equals the current datetime minus :alarm_duration:.
        The datetimes are all in UTC.

        :return: True if there is any active alarm, False otherwise
        """
        self.logger.debug("Checking for new alarms...")
        alarms = await self.get_alarms()
        if not alarms:
            return False
        for alarm in alarms:
            alarm_datetime = datetime.strptime(
                alarm["alarmDate"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            self.logger.debug(
                "Alarm " + str(alarm["alarmId"]) + " on " + str(alarm_datetime)
            )
            if alarm_datetime >= datetime.utcnow() - self.alarm_duration:
                self.logger.debug("Alarm " + str(alarm["alarmId"]) + " is active")
                self.logger.debug("There is an active alarm")
                return True
        self.logger.debug("No active alarm found")
        return False
