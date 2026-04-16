"""BlaulichtSMS API."""

import logging
from datetime import datetime, timedelta, timezone
from pprint import pformat

import aiohttp


class BlaulichtSmsSessionInitException(aiohttp.ClientError):
    """Exception for Session Init."""


class BlaulichtSmsAuthenticationError(aiohttp.ClientError):
    """Exception raised when authentication is rejected (e.g. 401/403)."""


class BlaulichtSmsController:
    """Handles the communication with the blaulichtSMS Dashboard API.

    See https://github.com/blaulichtSMS/docs/blob/master/dashboard_api_v1.md
    """

    def __init__(
        self,
        customer_id: str,
        username: str,
        password: str,
        alarm_duration: int = 3600,
        show_infos: bool = False,
        base_url: str = "https://api.blaulichtsms.net/blaulicht/api/alarm/v1/dashboard/",
        session: aiohttp.ClientSession | None = None,
    ):
        """Create new controller."""
        self.logger = logging.getLogger(__name__)

        self.customer_id = customer_id
        self.username = username
        self.password = password
        self.alarm_duration = timedelta(seconds=alarm_duration)
        self.show_infos = show_infos
        self.base_url = base_url

        self._session_token: str | None = None
        self._http_session = session

    def _session(self) -> aiohttp.ClientSession:
        """Return the injected aiohttp session or create a throwaway one."""
        if self._http_session is not None:
            return self._http_session
        return aiohttp.ClientSession()

    async def _request_json(self, method: str, url: str, **kwargs) -> dict:
        """Perform an HTTP request and return the parsed JSON body."""
        session = self._http_session
        if session is None:
            async with aiohttp.ClientSession() as owned, owned.request(
                method, url, **kwargs
            ) as resp:
                return await self._handle_response(resp)
        async with session.request(method, url, **kwargs) as resp:
            return await self._handle_response(resp)

    async def _handle_response(self, resp: aiohttp.ClientResponse) -> dict:
        """Raise on auth failure, otherwise return JSON body."""
        if resp.status in (401, 403):
            self._session_token = None
            raise BlaulichtSmsAuthenticationError(
                f"authentication rejected with status {resp.status}"
            )
        resp.raise_for_status()
        return await resp.json()

    async def get_session(self) -> str:
        """Request a new session token from the blaulichtSMS Dashboard API."""
        self.logger.debug("Initializing blaulichtSMS session...")
        content = {
            "customerId": self.customer_id,
            "username": self.username,
            "password": self.password,
        }
        try:
            json_body = await self._request_json(
                "POST", f"{self.base_url}login", json=content
            )
        except aiohttp.ClientError:
            self.logger.exception("blaulichtSMS login request failed")
            raise

        session_id = json_body.get("sessionId") if isinstance(json_body, dict) else None
        if not session_id:
            raise BlaulichtSmsSessionInitException(
                "blaulichtSMS login response missing sessionId"
            )
        self.logger.debug("Successfully initialized blaulichtSMS session")
        return session_id

    async def _ensure_session(self) -> str:
        """Return a valid session token, logging in if needed."""
        if not self._session_token:
            self._session_token = await self.get_session()
        return self._session_token

    async def get_alarms(self) -> list[dict]:
        """Get the alarms from the blaulichtSMS Dashboard API."""
        token = await self._ensure_session()
        self.logger.debug("Requesting blaulichtSMS alarms...")
        try:
            response_json = await self._request_json("GET", self.base_url + token)
        except BlaulichtSmsAuthenticationError:
            self.logger.info("session token rejected; retrying login")
            self._session_token = None
            token = await self._ensure_session()
            response_json = await self._request_json("GET", self.base_url + token)

        self.logger.debug("Response body:\n%s", pformat(response_json))
        alarms = response_json.get("alarms", [])
        if self.show_infos:
            alarms = alarms + response_json.get("infos", [])
        return alarms

    async def get_last_alarm(self) -> dict | None:
        """Get the most recent alarm, or None if there are none."""
        alarms = await self.get_alarms()
        if not alarms:
            return None
        alarms.sort(key=lambda a: a.get("alarmDate"), reverse=True)
        return alarms[0]

    async def get_anonymized_alarms(self) -> list[dict]:
        """Return alarms with PII removed."""
        alarms = await self.get_alarms()
        for a in alarms:
            a["recipients"] = len(
                [r for r in a.get("recipients", []) if r.get("participation") == "yes"]
            )
            a.pop("pointsOfInterest", None)
        return alarms

    async def is_alarm(self) -> bool:
        """Return True if any alarm is currently active."""
        self.logger.debug("Checking for active alarms...")
        alarms = await self.get_alarms()
        now = datetime.now(timezone.utc)
        for alarm in alarms:
            alarm_datetime = _parse_alarm_datetime(alarm.get("alarmDate"))
            if alarm_datetime is None:
                continue
            if alarm_datetime >= now - self.alarm_duration:
                self.logger.debug("Alarm %s is active", alarm.get("alarmId"))
                return True
        self.logger.debug("No active alarm found")
        return False


def _parse_alarm_datetime(raw: str | None) -> datetime | None:
    """Parse a blaulichtSMS alarm date string into a timezone-aware datetime."""
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
