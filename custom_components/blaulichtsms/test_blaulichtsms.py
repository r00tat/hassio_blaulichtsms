"""BlaulichtSMS tests."""

from typing import Any
from collections.abc import Coroutine
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import asyncio
import unittest
import os
import logging
import json

from .blaulichtsms import BlaulichtSmsController

log = logging.getLogger("TestBlaulichtSMS")


class TestBlaulichtsms(unittest.IsolatedAsyncioTestCase):
    """test blaulichtsms api."""

    async def asyncTearDown(self) -> Coroutine[Any, Any, None]:
        """Tear down tests."""
        await asyncio.sleep(0)
        return await super().asyncTearDown()

    async def test_auth(self):
        """Test auth."""
        if os.environ.get("SKIP_INTEGRATION_TEST"):
            log.info("skipping integration test: test_auth")
            return
        log.info("tesing auth")
        blaulichtsms = BlaulichtSmsController(
            os.environ["BLAULICHTSMS_CUSTOMERID"],
            os.environ["BLAULICHTSMS_USERNAME"],
            os.environ["BLAULICHTSMS_PASSWORD"],
        )
        token = await blaulichtsms.get_session()
        log.info("token: %s", token)
        self.assertIsNotNone(token)

    async def test_alarms(self):
        """Get alarms."""
        if os.environ.get("SKIP_INTEGRATION_TEST"):
            log.info("skipping integration test: test_alarms")
            return
        log.info("fetching alarms")
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

        log.info("fetch last alarm")
        alarm = await blaulichtsms.get_last_alarm()

        if len(alarms) == 0:
            self.assertIsNone(alarm)
        else:
            self.assertIsNotNone(alarm)
            log.info("alarm %s on %s", alarm.get("alarmText"), alarm.get("alarmDate"))


def _make_alarm(alarm_id="A1", minutes_ago=0, recipients=None):
    """Build a minimal alarm dict for tests."""
    alarm_date = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return {
        "alarmId": alarm_id,
        "alarmDate": alarm_date.isoformat(),
        "recipients": recipients or [],
    }


class TestNewAlarmActiveSensor(unittest.TestCase):
    """Unit tests for BlaulichtSMSNewAlarmActiveSensor."""

    def _make_sensor(self, track_recipient=None, new_alarm_duration=300):
        from .binary_sensor import BlaulichtSMSNewAlarmActiveSensor

        coordinator = MagicMock()
        coordinator.data = None
        coordinator.api = MagicMock()
        coordinator.api.customer_id = "cust-1"
        # CoordinatorEntity.__init__ calls async_add_listener; MagicMock handles that.
        sensor = BlaulichtSMSNewAlarmActiveSensor(
            coordinator,
            MagicMock(),  # hass
            new_alarm_duration,
            track_recipient,
        )
        # async_write_ha_state touches HA internals; replace with a recorder.
        sensor.async_write_ha_state = MagicMock()
        return sensor, coordinator

    def test_evaluate_target_within_window_no_track(self):
        """Fresh alarm without track_recipient returns True."""
        sensor, _ = self._make_sensor()
        alarm = _make_alarm(minutes_ago=1)
        self.assertTrue(sensor._evaluate_target(alarm))

    def test_evaluate_target_outside_window_no_track(self):
        """Alarm older than the window returns False."""
        sensor, _ = self._make_sensor()
        alarm = _make_alarm(minutes_ago=10)
        self.assertFalse(sensor._evaluate_target(alarm))

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
        """Tracked recipient not in list returns False."""
        sensor, _ = self._make_sensor(track_recipient="+4312345")
        alarm = _make_alarm(minutes_ago=1, recipients=[])
        self.assertFalse(sensor._evaluate_target(alarm))

    def test_evaluate_target_track_recipient_yes_but_expired(self):
        """Late confirmation after window expired stays False."""
        sensor, _ = self._make_sensor(track_recipient="+4312345")
        alarm = _make_alarm(
            minutes_ago=10,
            recipients=[{"msisdn": "+4312345", "participation": "yes"}],
        )
        self.assertFalse(sensor._evaluate_target(alarm))

    def test_new_alarm_forces_false_then_true(self):
        """A new alarm id triggers two state writes in one cycle."""
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = True
        sensor._last_alarm_id = "OLD"
        coordinator.data = _make_alarm(alarm_id="NEW", minutes_ago=1)

        sensor._handle_coordinator_update()

        calls = sensor.async_write_ha_state.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertTrue(sensor._attr_is_on)
        self.assertEqual(sensor._last_alarm_id, "NEW")

    def test_new_alarm_writes_false_before_true(self):
        """The forced False write happens before the True write."""
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = True
        sensor._last_alarm_id = "OLD"
        coordinator.data = _make_alarm(alarm_id="NEW", minutes_ago=1)

        captured = []
        sensor.async_write_ha_state = MagicMock(
            side_effect=lambda: captured.append(sensor._attr_is_on)
        )

        sensor._handle_coordinator_update()

        self.assertEqual(captured, [False, True])

    def test_same_alarm_stable_no_extra_false_write(self):
        """Unchanged alarm id does not produce spurious writes."""
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = True
        sensor._last_alarm_id = "SAME"
        coordinator.data = _make_alarm(alarm_id="SAME", minutes_ago=1)

        sensor._handle_coordinator_update()

        sensor.async_write_ha_state.assert_not_called()
        self.assertTrue(sensor._attr_is_on)

    def test_new_alarm_outside_window_stays_false(self):
        """New alarm outside the window emits only the forced False."""
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = False
        sensor._last_alarm_id = None
        coordinator.data = _make_alarm(alarm_id="NEW", minutes_ago=10)

        captured = []
        sensor.async_write_ha_state = MagicMock(
            side_effect=lambda: captured.append(sensor._attr_is_on)
        )

        sensor._handle_coordinator_update()

        self.assertEqual(captured, [False])
        self.assertFalse(sensor._attr_is_on)

    def test_late_confirmation_flips_to_true(self):
        """A later confirmation on the same alarm flips to True."""
        sensor, coordinator = self._make_sensor(track_recipient="+4312345")
        coordinator.data = _make_alarm(
            alarm_id="NEW",
            minutes_ago=1,
            recipients=[{"msisdn": "+4312345", "participation": "pending"}],
        )
        sensor._handle_coordinator_update()
        self.assertFalse(sensor._attr_is_on)

        coordinator.data = _make_alarm(
            alarm_id="NEW",
            minutes_ago=2,
            recipients=[{"msisdn": "+4312345", "participation": "yes"}],
        )
        sensor.async_write_ha_state.reset_mock()
        sensor._handle_coordinator_update()

        self.assertTrue(sensor._attr_is_on)
        sensor.async_write_ha_state.assert_called_once()

    def test_no_data_stays_off(self):
        """Missing coordinator data turns a True sensor off with one write."""
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = True
        coordinator.data = None

        sensor._handle_coordinator_update()

        self.assertFalse(sensor._attr_is_on)
        sensor.async_write_ha_state.assert_called_once()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
