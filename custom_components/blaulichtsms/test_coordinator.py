"""Unit tests for BlaulichtSMSCoordinator."""

import unittest
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock

from ._test_fixtures import make_alarm


class TestCoordinatorIsAlarmActive(unittest.TestCase):
    """Tests for BlaulichtSMSCoordinator._is_alarm_active."""

    def _make_coordinator(self, alarm_duration_seconds=3600):
        """Construct a coordinator with a stubbed api for _is_alarm_active tests."""
        from .coordinator import BlaulichtSMSCoordinator

        coordinator = BlaulichtSMSCoordinator.__new__(BlaulichtSMSCoordinator)
        coordinator.api = MagicMock()
        coordinator.api.alarm_duration = timedelta(seconds=alarm_duration_seconds)
        return coordinator

    def test_none_alarm_is_inactive(self):
        """A None alarm is never active."""
        coordinator = self._make_coordinator()
        self.assertFalse(coordinator._is_alarm_active(None))

    def test_recent_alarm_is_active(self):
        """A recent alarm within alarm_duration is active."""
        coordinator = self._make_coordinator()
        self.assertTrue(coordinator._is_alarm_active(make_alarm(minutes_ago=10)))

    def test_old_alarm_is_inactive(self):
        """An alarm older than alarm_duration is inactive."""
        coordinator = self._make_coordinator()
        self.assertFalse(coordinator._is_alarm_active(make_alarm(minutes_ago=120)))

    def test_end_date_in_future_is_active(self):
        """End date in the future overrides an expired alarm_duration."""
        coordinator = self._make_coordinator(alarm_duration_seconds=10)
        alarm = make_alarm(minutes_ago=120, end_minutes_ahead=5)
        self.assertTrue(coordinator._is_alarm_active(alarm))

    def test_end_date_in_past_is_inactive(self):
        """End date in the past overrides a fresh alarm_duration."""
        coordinator = self._make_coordinator(alarm_duration_seconds=3600)
        alarm = make_alarm(minutes_ago=5)
        alarm["endDate"] = (
            datetime.now(UTC) - timedelta(minutes=1)
        ).isoformat()
        self.assertFalse(coordinator._is_alarm_active(alarm))

    def test_missing_alarm_date_is_inactive(self):
        """An alarm without alarmDate and no endDate is inactive."""
        coordinator = self._make_coordinator()
        self.assertFalse(coordinator._is_alarm_active({"alarmId": "X"}))


if __name__ == "__main__":
    unittest.main()
