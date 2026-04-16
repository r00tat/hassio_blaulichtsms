"""Unit tests for the BlaulichtSMS binary sensors."""

import unittest
from unittest.mock import MagicMock

from ._test_fixtures import make_alarm, wrap


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
        self.assertTrue(sensor._evaluate_target(make_alarm(minutes_ago=1)))

    def test_evaluate_target_outside_window_no_track(self):
        """Alarm older than the window returns False."""
        sensor, _ = self._make_sensor()
        self.assertFalse(sensor._evaluate_target(make_alarm(minutes_ago=10)))

    def test_evaluate_target_track_recipient_yes(self):
        """Tracked recipient with participation=yes returns True."""
        sensor, _ = self._make_sensor(track_recipient="+4312345")
        alarm = make_alarm(
            minutes_ago=1,
            recipients=[{"msisdn": "+4312345", "participation": "yes"}],
        )
        self.assertTrue(sensor._evaluate_target(alarm))

    def test_evaluate_target_track_recipient_no_confirmation(self):
        """Tracked recipient without yes returns False."""
        sensor, _ = self._make_sensor(track_recipient="+4312345")
        alarm = make_alarm(
            minutes_ago=1,
            recipients=[{"msisdn": "+4312345", "participation": "no"}],
        )
        self.assertFalse(sensor._evaluate_target(alarm))

    def test_evaluate_target_track_recipient_missing(self):
        """Tracked recipient missing from alarm payload returns False."""
        sensor, _ = self._make_sensor(track_recipient="+4312345")
        self.assertFalse(
            sensor._evaluate_target(make_alarm(minutes_ago=1, recipients=[]))
        )

    def test_evaluate_target_track_recipient_yes_but_expired(self):
        """Expired window returns False even with a yes confirmation."""
        sensor, _ = self._make_sensor(track_recipient="+4312345")
        alarm = make_alarm(
            minutes_ago=10,
            recipients=[{"msisdn": "+4312345", "participation": "yes"}],
        )
        self.assertFalse(sensor._evaluate_target(alarm))

    def test_new_alarm_forces_false_then_true(self):
        """New alarm id flips is_on False then re-evaluates to True."""
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = True
        sensor._last_alarm_id = "OLD"
        coordinator.data = wrap(make_alarm(alarm_id="NEW", minutes_ago=1))

        sensor._handle_coordinator_update()

        self.assertEqual(len(sensor.async_write_ha_state.call_args_list), 2)
        self.assertTrue(sensor._attr_is_on)
        self.assertEqual(sensor._last_alarm_id, "NEW")

    def test_new_alarm_writes_false_before_true(self):
        """State writes happen in order: False, then True."""
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = True
        sensor._last_alarm_id = "OLD"
        coordinator.data = wrap(make_alarm(alarm_id="NEW", minutes_ago=1))

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
        coordinator.data = wrap(make_alarm(alarm_id="SAME", minutes_ago=1))

        sensor._handle_coordinator_update()

        sensor.async_write_ha_state.assert_not_called()
        self.assertTrue(sensor._attr_is_on)

    def test_new_alarm_outside_window_stays_false(self):
        """New alarm outside its window leaves is_on False."""
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = False
        sensor._last_alarm_id = None
        coordinator.data = wrap(make_alarm(alarm_id="NEW", minutes_ago=10))

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
        coordinator.data = wrap(
            make_alarm(
                alarm_id="NEW",
                minutes_ago=1,
                recipients=[{"msisdn": "+4312345", "participation": "pending"}],
            )
        )
        sensor._handle_coordinator_update()
        self.assertFalse(sensor._attr_is_on)

        coordinator.data = wrap(
            make_alarm(
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


class TestNeedsAcknowledgementSensor(unittest.TestCase):
    """Tests for BlaulichtSMSNeedsAcknowledgementSensor."""

    def _make_sensor(self):
        """Construct the sensor with a stubbed coordinator."""
        from .binary_sensor import BlaulichtSMSNeedsAcknowledgementSensor

        coordinator = MagicMock()
        coordinator.data = None
        coordinator.api = MagicMock()
        coordinator.api.customer_id = "cust-1"
        sensor = BlaulichtSMSNeedsAcknowledgementSensor(coordinator)
        sensor.async_write_ha_state = MagicMock()
        return sensor, coordinator

    def test_off_when_no_data(self):
        """Sensor stays off when coordinator has no data yet."""
        sensor, coordinator = self._make_sensor()
        coordinator.data = None
        sensor._handle_coordinator_update()
        self.assertFalse(sensor._attr_is_on)

    def test_off_when_no_alarm(self):
        """Sensor stays off when there is no alarm."""
        sensor, coordinator = self._make_sensor()
        coordinator.data = {"alarm": None, "is_active": False}
        sensor._handle_coordinator_update()
        self.assertFalse(sensor._attr_is_on)

    def test_on_when_needs_acknowledgement_true(self):
        """Sensor turns on when needsAcknowledgement is True."""
        sensor, coordinator = self._make_sensor()
        coordinator.data = {
            "alarm": {"alarmId": "A", "needsAcknowledgement": True},
            "is_active": True,
        }
        sensor._handle_coordinator_update()
        self.assertTrue(sensor._attr_is_on)

    def test_off_when_needs_acknowledgement_false(self):
        """Sensor stays off when needsAcknowledgement is False."""
        sensor, coordinator = self._make_sensor()
        coordinator.data = {
            "alarm": {"alarmId": "A", "needsAcknowledgement": False},
            "is_active": True,
        }
        sensor._handle_coordinator_update()
        self.assertFalse(sensor._attr_is_on)

    def test_off_when_field_missing(self):
        """Missing field is treated as False."""
        sensor, coordinator = self._make_sensor()
        coordinator.data = {"alarm": {"alarmId": "A"}, "is_active": True}
        sensor._handle_coordinator_update()
        self.assertFalse(sensor._attr_is_on)


class TestBinarySensorIcons(unittest.TestCase):
    """Verify icons, German names and stable entity_id slug on binary sensors."""

    def _coordinator(self):
        coordinator = MagicMock()
        coordinator.data = None
        coordinator.api = MagicMock()
        coordinator.api.customer_id = "cust-1"
        return coordinator

    def test_alarm_active_sensor_icon(self):
        """AlarmActive uses an alarm-light icon."""
        from .binary_sensor import BlaulichtSMSAlarmActiveSensor

        sensor = BlaulichtSMSAlarmActiveSensor(self._coordinator())
        self.assertEqual(sensor._attr_icon, "mdi:alarm-light")

    def test_needs_acknowledgement_icon(self):
        """NeedsAcknowledgement uses a bell-alert outline icon."""
        from .binary_sensor import BlaulichtSMSNeedsAcknowledgementSensor

        sensor = BlaulichtSMSNeedsAcknowledgementSensor(self._coordinator())
        self.assertEqual(sensor._attr_icon, "mdi:bell-alert-outline")

    def test_new_alarm_active_icon(self):
        """NewAlarmActive uses a bell-alert icon."""
        from .binary_sensor import BlaulichtSMSNewAlarmActiveSensor

        sensor = BlaulichtSMSNewAlarmActiveSensor(self._coordinator(), 300, None)
        self.assertEqual(sensor._attr_icon, "mdi:bell-alert")

    def test_german_display_names(self):
        """Binary sensors expose German display names."""
        from .binary_sensor import (
            BlaulichtSMSAlarmActiveSensor,
            BlaulichtSMSNeedsAcknowledgementSensor,
            BlaulichtSMSNewAlarmActiveSensor,
        )

        self.assertEqual(
            BlaulichtSMSAlarmActiveSensor(self._coordinator())._attr_name,
            "BlaulichtSMS Alarm aktiv",
        )
        self.assertEqual(
            BlaulichtSMSNeedsAcknowledgementSensor(self._coordinator())._attr_name,
            "BlaulichtSMS Bestätigung erforderlich",
        )
        self.assertEqual(
            BlaulichtSMSNewAlarmActiveSensor(
                self._coordinator(), 300, None
            )._attr_name,
            "BlaulichtSMS Neuer Alarm aktiv",
        )

    def test_suggested_object_id_preserves_old_slug(self):
        """suggested_object_id matches the pre-rename entity_id for new installs."""
        from .binary_sensor import (
            BlaulichtSMSAlarmActiveSensor,
            BlaulichtSMSNeedsAcknowledgementSensor,
            BlaulichtSMSNewAlarmActiveSensor,
        )

        self.assertEqual(
            BlaulichtSMSAlarmActiveSensor(self._coordinator()).suggested_object_id,
            "blaulichtsms_alarm_active",
        )
        self.assertEqual(
            BlaulichtSMSNeedsAcknowledgementSensor(
                self._coordinator()
            ).suggested_object_id,
            "blaulichtsms_needs_acknowledgement",
        )
        self.assertEqual(
            BlaulichtSMSNewAlarmActiveSensor(
                self._coordinator(), 300, None
            ).suggested_object_id,
            "blaulichtsms_new_alarm_active",
        )

    def test_unique_id_preserved(self):
        """unique_id keeps the stable blsms-{customer_id}-{key} format."""
        from .binary_sensor import (
            BlaulichtSMSAlarmActiveSensor,
            BlaulichtSMSNeedsAcknowledgementSensor,
            BlaulichtSMSNewAlarmActiveSensor,
        )

        self.assertEqual(
            BlaulichtSMSAlarmActiveSensor(self._coordinator())._attr_unique_id,
            "blsms-cust-1-alarm-active",
        )
        self.assertEqual(
            BlaulichtSMSNeedsAcknowledgementSensor(
                self._coordinator()
            )._attr_unique_id,
            "blsms-cust-1-needs-acknowledgement",
        )
        self.assertEqual(
            BlaulichtSMSNewAlarmActiveSensor(
                self._coordinator(), 300, None
            )._attr_unique_id,
            "blsms-cust-1-new-alarm-active",
        )


if __name__ == "__main__":
    unittest.main()
