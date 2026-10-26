"""Shared fixtures for BlaulichtSMS tests.

Not picked up by unittest discovery (filename does not match ``test*.py``).
"""

from datetime import datetime, timedelta, UTC


def make_alarm(alarm_id="A1", minutes_ago=0, recipients=None, end_minutes_ahead=None):
    """Build a minimal alarm dict for tests."""
    alarm_date = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    alarm = {
        "alarmId": alarm_id,
        "alarmDate": alarm_date.isoformat(),
        "recipients": recipients or [],
    }
    if end_minutes_ahead is not None:
        alarm["endDate"] = (
            datetime.now(UTC) + timedelta(minutes=end_minutes_ahead)
        ).isoformat()
    return alarm


def wrap(alarm, *, is_active=None):
    """Build the coordinator.data shape used by all entities."""
    if alarm is None:
        return {"alarm": None, "is_active": False}
    if is_active is None:
        alarm_date_raw = alarm.get("alarmDate")
        alarm_date = datetime.fromisoformat(alarm_date_raw) if alarm_date_raw else None
        is_active = (
            alarm_date is not None
            and datetime.now(alarm_date.tzinfo) < alarm_date + timedelta(seconds=300)
        )
    return {"alarm": alarm, "is_active": is_active}
