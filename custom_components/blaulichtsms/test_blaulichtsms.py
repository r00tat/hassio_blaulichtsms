"""BlaulichtSMS tests."""

import asyncio
import json
import logging
import os
import unittest
from collections.abc import Coroutine
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

from .blaulichtsms import BlaulichtSmsController

log = logging.getLogger("TestBlaulichtSMS")


class TestBlaulichtsms(unittest.IsolatedAsyncioTestCase):
    """Integration tests that hit the real API. Gated by SKIP_INTEGRATION_TEST."""

    async def asyncTearDown(self) -> Coroutine[Any, Any, None]:
        """Tear down tests."""
        await asyncio.sleep(0)
        return await super().asyncTearDown()

    async def test_auth(self):
        """Test auth."""
        if os.environ.get("SKIP_INTEGRATION_TEST"):
            log.info("skipping integration test: test_auth")
            return
        blaulichtsms = BlaulichtSmsController(
            os.environ["BLAULICHTSMS_CUSTOMERID"],
            os.environ["BLAULICHTSMS_USERNAME"],
            os.environ["BLAULICHTSMS_PASSWORD"],
        )
        token = await blaulichtsms.get_session()
        self.assertIsNotNone(token)

    async def test_alarms(self):
        """Get alarms."""
        if os.environ.get("SKIP_INTEGRATION_TEST"):
            log.info("skipping integration test: test_alarms")
            return
        blaulichtsms = BlaulichtSmsController(
            os.environ["BLAULICHTSMS_CUSTOMERID"],
            os.environ["BLAULICHTSMS_USERNAME"],
            os.environ["BLAULICHTSMS_PASSWORD"],
        )
        alarms = await blaulichtsms.get_anonymized_alarms()
        self.assertIsNotNone(alarms)
        log.info("alarms %s", json.dumps(alarms))
        self.assertGreaterEqual(len(alarms), 0)

    async def test_get_last_alarm(self):
        """Get last alarm."""
        if os.environ.get("SKIP_INTEGRATION_TEST"):
            log.info("skipping integration test: test_get_last_alarm")
            return
        blaulichtsms = BlaulichtSmsController(
            os.environ["BLAULICHTSMS_CUSTOMERID"],
            os.environ["BLAULICHTSMS_USERNAME"],
            os.environ["BLAULICHTSMS_PASSWORD"],
        )

        alarms = await blaulichtsms.get_anonymized_alarms()
        self.assertIsNotNone(alarms)

        alarm = await blaulichtsms.get_last_alarm()

        if len(alarms) == 0:
            self.assertIsNone(alarm)
        else:
            self.assertIsNotNone(alarm)


def _make_alarm(alarm_id="A1", minutes_ago=0, recipients=None, end_minutes_ahead=None):
    """Build a minimal alarm dict for tests."""
    alarm_date = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    alarm = {
        "alarmId": alarm_id,
        "alarmDate": alarm_date.isoformat(),
        "recipients": recipients or [],
    }
    if end_minutes_ahead is not None:
        alarm["endDate"] = (
            datetime.now(timezone.utc) + timedelta(minutes=end_minutes_ahead)
        ).isoformat()
    return alarm


def _wrap(alarm, *, is_active=None):
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


class TestNewAlarmActiveSensor(unittest.TestCase):
    """Unit tests for BlaulichtSMSNewAlarmActiveSensor."""

    def _make_sensor(self, track_recipient=None, new_alarm_duration=300):
        """Construct a sensor with a stubbed coordinator."""
        from .binary_sensor import BlaulichtSMSNewAlarmActiveSensor

        coordinator = MagicMock()
        coordinator.data = None
        coordinator.api = MagicMock()
        coordinator.api.customer_id = "cust-1"
        sensor = BlaulichtSMSNewAlarmActiveSensor(
            coordinator,
            new_alarm_duration,
            track_recipient,
        )
        sensor.async_write_ha_state = MagicMock()
        return sensor, coordinator

    def test_evaluate_target_within_window_no_track(self):
        """Fresh alarm without track_recipient returns True."""
        sensor, _ = self._make_sensor()
        self.assertTrue(sensor._evaluate_target(_make_alarm(minutes_ago=1)))

    def test_evaluate_target_outside_window_no_track(self):
        """Alarm older than the window returns False."""
        sensor, _ = self._make_sensor()
        self.assertFalse(sensor._evaluate_target(_make_alarm(minutes_ago=10)))

    def test_evaluate_target_track_recipient_yes(self):
        """Tracked recipient with participation=yes returns True."""
        sensor, _ = self._make_sensor(track_recipient="+4312345")
        alarm = _make_alarm(
            minutes_ago=1,
            recipients=[{"msisdn": "+4312345", "participation": "yes"}],
        )
        self.assertTrue(sensor._evaluate_target(alarm))

    def test_evaluate_target_track_recipient_no_confirmation(self):
        """Tracked recipient without yes returns False."""
        sensor, _ = self._make_sensor(track_recipient="+4312345")
        alarm = _make_alarm(
            minutes_ago=1,
            recipients=[{"msisdn": "+4312345", "participation": "no"}],
        )
        self.assertFalse(sensor._evaluate_target(alarm))

    def test_evaluate_target_track_recipient_missing(self):
        """Tracked recipient missing from alarm payload returns False."""
        sensor, _ = self._make_sensor(track_recipient="+4312345")
        self.assertFalse(
            sensor._evaluate_target(_make_alarm(minutes_ago=1, recipients=[]))
        )

    def test_evaluate_target_track_recipient_yes_but_expired(self):
        """Expired window returns False even with a yes confirmation."""
        sensor, _ = self._make_sensor(track_recipient="+4312345")
        alarm = _make_alarm(
            minutes_ago=10,
            recipients=[{"msisdn": "+4312345", "participation": "yes"}],
        )
        self.assertFalse(sensor._evaluate_target(alarm))

    def test_new_alarm_forces_false_then_true(self):
        """New alarm id flips is_on False then re-evaluates to True."""
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = True
        sensor._last_alarm_id = "OLD"
        coordinator.data = _wrap(_make_alarm(alarm_id="NEW", minutes_ago=1))

        sensor._handle_coordinator_update()

        self.assertEqual(len(sensor.async_write_ha_state.call_args_list), 2)
        self.assertTrue(sensor._attr_is_on)
        self.assertEqual(sensor._last_alarm_id, "NEW")

    def test_new_alarm_writes_false_before_true(self):
        """State writes happen in order: False, then True."""
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = True
        sensor._last_alarm_id = "OLD"
        coordinator.data = _wrap(_make_alarm(alarm_id="NEW", minutes_ago=1))

        captured = []
        sensor.async_write_ha_state = MagicMock(
            side_effect=lambda: captured.append(sensor._attr_is_on)
        )

        sensor._handle_coordinator_update()

        self.assertEqual(captured, [False, True])

    def test_same_alarm_stable_no_extra_false_write(self):
        """Same alarm id with stable state writes nothing."""
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = True
        sensor._last_alarm_id = "SAME"
        coordinator.data = _wrap(_make_alarm(alarm_id="SAME", minutes_ago=1))

        sensor._handle_coordinator_update()

        sensor.async_write_ha_state.assert_not_called()
        self.assertTrue(sensor._attr_is_on)

    def test_new_alarm_outside_window_stays_false(self):
        """New alarm outside its window leaves is_on False."""
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = False
        sensor._last_alarm_id = None
        coordinator.data = _wrap(_make_alarm(alarm_id="NEW", minutes_ago=10))

        captured = []
        sensor.async_write_ha_state = MagicMock(
            side_effect=lambda: captured.append(sensor._attr_is_on)
        )

        sensor._handle_coordinator_update()

        self.assertEqual(captured, [False])
        self.assertFalse(sensor._attr_is_on)

    def test_late_confirmation_flips_to_true(self):
        """A recipient confirming later flips is_on to True."""
        sensor, coordinator = self._make_sensor(track_recipient="+4312345")
        coordinator.data = _wrap(
            _make_alarm(
                alarm_id="NEW",
                minutes_ago=1,
                recipients=[{"msisdn": "+4312345", "participation": "pending"}],
            )
        )
        sensor._handle_coordinator_update()
        self.assertFalse(sensor._attr_is_on)

        coordinator.data = _wrap(
            _make_alarm(
                alarm_id="NEW",
                minutes_ago=2,
                recipients=[{"msisdn": "+4312345", "participation": "yes"}],
            )
        )
        sensor.async_write_ha_state.reset_mock()
        sensor._handle_coordinator_update()

        self.assertTrue(sensor._attr_is_on)
        sensor.async_write_ha_state.assert_called_once()

    def test_no_data_stays_off(self):
        """Missing coordinator data turns the sensor off."""
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = True
        coordinator.data = None

        sensor._handle_coordinator_update()

        self.assertFalse(sensor._attr_is_on)
        sensor.async_write_ha_state.assert_called_once()


class TestAlarmActiveSensor(unittest.TestCase):
    """Tests for the `is_active`-driven BlaulichtSMSAlarmActiveSensor."""

    def _make_sensor(self):
        """Construct an AlarmActive sensor with a stubbed coordinator."""
        from .binary_sensor import BlaulichtSMSAlarmActiveSensor

        coordinator = MagicMock()
        coordinator.data = None
        coordinator.api = MagicMock()
        coordinator.api.customer_id = "cust-1"
        sensor = BlaulichtSMSAlarmActiveSensor(coordinator)
        sensor.async_write_ha_state = MagicMock()
        return sensor, coordinator

    def test_off_when_no_data(self):
        """Sensor stays off when coordinator has no data yet."""
        sensor, coordinator = self._make_sensor()
        coordinator.data = None
        sensor._handle_coordinator_update()
        self.assertFalse(sensor._attr_is_on)

    def test_on_when_is_active_true(self):
        """Sensor turns on when coordinator signals is_active=True."""
        sensor, coordinator = self._make_sensor()
        coordinator.data = {"alarm": {"alarmId": "A"}, "is_active": True}
        sensor._handle_coordinator_update()
        self.assertTrue(sensor._attr_is_on)

    def test_off_when_is_active_false(self):
        """Sensor turns off when coordinator signals is_active=False."""
        sensor, coordinator = self._make_sensor()
        coordinator.data = {"alarm": {"alarmId": "A"}, "is_active": False}
        sensor._handle_coordinator_update()
        self.assertFalse(sensor._attr_is_on)


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
        self.assertTrue(coordinator._is_alarm_active(_make_alarm(minutes_ago=10)))

    def test_old_alarm_is_inactive(self):
        """An alarm older than alarm_duration is inactive."""
        coordinator = self._make_coordinator()
        self.assertFalse(
            coordinator._is_alarm_active(_make_alarm(minutes_ago=120))
        )

    def test_end_date_in_future_is_active(self):
        """End date in the future overrides an expired alarm_duration."""
        coordinator = self._make_coordinator(alarm_duration_seconds=10)
        alarm = _make_alarm(minutes_ago=120, end_minutes_ahead=5)
        self.assertTrue(coordinator._is_alarm_active(alarm))

    def test_end_date_in_past_is_inactive(self):
        """End date in the past overrides a fresh alarm_duration."""
        coordinator = self._make_coordinator(alarm_duration_seconds=3600)
        alarm = _make_alarm(minutes_ago=5)
        alarm["endDate"] = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        ).isoformat()
        self.assertFalse(coordinator._is_alarm_active(alarm))

    def test_missing_alarm_date_is_inactive(self):
        """An alarm without alarmDate and no endDate is inactive."""
        coordinator = self._make_coordinator()
        self.assertFalse(coordinator._is_alarm_active({"alarmId": "X"}))


class TestSensorEntity(unittest.TestCase):
    """Tests for the generic BlaulichtSMSEntity using the wrapped data shape."""

    def _make_sensor(self, attribute, config_data=None):
        """Construct a BlaulichtSMSEntity with a stubbed coordinator."""
        from .sensor import BlaulichtSMSEntity

        coordinator = MagicMock()
        coordinator.data = None
        coordinator.api = MagicMock()
        coordinator.api.customer_id = "cust-1"
        config = MagicMock()
        config.data = config_data or {}
        sensor = BlaulichtSMSEntity(coordinator, attribute, config)
        sensor.async_write_ha_state = MagicMock()
        return sensor, coordinator

    def test_alarm_text_replaces_slash(self):
        """Alarm text values get spaced slashes."""
        sensor, coordinator = self._make_sensor("alarmText")
        coordinator.data = _wrap({"alarmText": "B4/Brand"})
        sensor._handle_coordinator_update()
        self.assertEqual(sensor._attr_native_value, "B4 / Brand")

    def test_track_recipient_missing_returns_unknown(self):
        """Missing recipient yields 'unknown' rather than raising."""
        sensor, coordinator = self._make_sensor(
            "track_recipient",
            config_data={"track_recipient": "+4399"},
        )
        coordinator.data = _wrap({"recipients": []})
        sensor._handle_coordinator_update()
        self.assertEqual(sensor._attr_native_value, "unknown")

    def test_track_recipient_found(self):
        """Found recipient returns their participation value."""
        sensor, coordinator = self._make_sensor(
            "track_recipient",
            config_data={"track_recipient": "+4399"},
        )
        coordinator.data = _wrap(
            {"recipients": [{"msisdn": "+4399", "participation": "yes"}]}
        )
        sensor._handle_coordinator_update()
        self.assertEqual(sensor._attr_native_value, "yes")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
