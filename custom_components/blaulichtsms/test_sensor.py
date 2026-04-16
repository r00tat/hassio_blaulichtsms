"""Unit tests for the BlaulichtSMS sensor entities and pure helpers."""

import unittest
from unittest.mock import MagicMock

from ._test_fixtures import wrap


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
        coordinator.data = wrap({"alarmText": "B4/Brand"})
        sensor._handle_coordinator_update()
        self.assertEqual(sensor._attr_native_value, "B4 / Brand")

    def test_track_recipient_missing_returns_unknown(self):
        """Missing recipient yields 'unknown' rather than raising."""
        sensor, coordinator = self._make_sensor(
            "track_recipient",
            config_data={"track_recipient": "+4399"},
        )
        coordinator.data = wrap({"recipients": []})
        sensor._handle_coordinator_update()
        self.assertEqual(sensor._attr_native_value, "unknown")

    def test_track_recipient_found(self):
        """Found recipient returns their participation value."""
        sensor, coordinator = self._make_sensor(
            "track_recipient",
            config_data={"track_recipient": "+4399"},
        )
        coordinator.data = wrap(
            {"recipients": [{"msisdn": "+4399", "participation": "yes"}]}
        )
        sensor._handle_coordinator_update()
        self.assertEqual(sensor._attr_native_value, "yes")

    def test_recipients_yes_count(self):
        """recipients_yes sensor counts participation=='yes'."""
        sensor, coordinator = self._make_sensor("recipients_yes")
        coordinator.data = wrap(
            {
                "recipients": [
                    {"participation": "yes"},
                    {"participation": "yes"},
                    {"participation": "no"},
                    {"participation": "pending"},
                ]
            }
        )
        sensor._handle_coordinator_update()
        self.assertEqual(sensor._attr_native_value, 2)

    def test_recipients_total_count(self):
        """recipients_total sensor counts the full list."""
        sensor, coordinator = self._make_sensor("recipients_total")
        coordinator.data = wrap({"recipients": [{"participation": "yes"}] * 3})
        sensor._handle_coordinator_update()
        self.assertEqual(sensor._attr_native_value, 3)

    def test_recipients_no_and_pending_counts(self):
        """recipients_no and recipients_pending compute their respective counts."""
        recipients = [
            {"participation": "no"},
            {"participation": "no"},
            {"participation": "pending"},
        ]
        sensor_no, coord_no = self._make_sensor("recipients_no")
        coord_no.data = wrap({"recipients": recipients})
        sensor_no._handle_coordinator_update()
        self.assertEqual(sensor_no._attr_native_value, 2)

        sensor_pending, coord_p = self._make_sensor("recipients_pending")
        coord_p.data = wrap({"recipients": recipients})
        sensor_pending._handle_coordinator_update()
        self.assertEqual(sensor_pending._attr_native_value, 1)

    def test_recipients_count_missing_field(self):
        """recipients_* sensors degrade to 0 when the recipients field is absent."""
        sensor, coordinator = self._make_sensor("recipients_total")
        coordinator.data = wrap({"alarmId": "A"})
        sensor._handle_coordinator_update()
        self.assertEqual(sensor._attr_native_value, 0)

    def test_confirmed_by_function_state_and_attrs(self):
        """confirmed_by_function uses function count as state and exposes detail array."""
        sensor, coordinator = self._make_sensor("confirmed_by_function")
        f_ats = {
            "functionId": "F1",
            "name": "ATS Träger",
            "shortForm": "ATS",
            "order": 1,
            "backgroundHexColorCode": "#ebfa57",
            "foregroundHexColorCode": "#000000",
        }
        f_tmb = {
            "functionId": "F2",
            "name": "TMB Maschinist",
            "shortForm": "TMB",
            "order": 2,
            "backgroundHexColorCode": "#5bc0de",
            "foregroundHexColorCode": "#ffffff",
        }
        coordinator.data = wrap(
            {
                "recipients": [
                    {"participation": "yes", "functions": [f_ats, f_tmb]},
                    {"participation": "yes", "functions": [f_ats]},
                    {"participation": "pending", "functions": [f_tmb]},
                ]
            }
        )
        sensor._handle_coordinator_update()
        self.assertEqual(sensor._attr_native_value, 2)  # two distinct functions
        attrs = sensor._attr_extra_state_attributes["functions"]
        self.assertEqual([a["shortForm"] for a in attrs], ["ATS", "TMB"])
        self.assertEqual(attrs[0]["yes"], 2)
        self.assertEqual(attrs[1]["yes"], 1)
        self.assertEqual(attrs[1]["pending"], 1)
        self.assertEqual(attrs[0]["backgroundColor"], "#ebfa57")

    def test_confirmed_by_function_empty_recipients(self):
        """With no recipients, state is 0 and attribute array is empty."""
        sensor, coordinator = self._make_sensor("confirmed_by_function")
        coordinator.data = wrap({"recipients": []})
        sensor._handle_coordinator_update()
        self.assertEqual(sensor._attr_native_value, 0)
        self.assertEqual(sensor._attr_extra_state_attributes["functions"], [])

    def test_address_sensor(self):
        """Address sensor returns geolocation.address or None."""
        sensor, coordinator = self._make_sensor("address")
        coordinator.data = wrap(
            {"geolocation": {"address": "Hauptplatz 1, 7100 Neusiedl"}}
        )
        sensor._handle_coordinator_update()
        self.assertEqual(sensor._attr_native_value, "Hauptplatz 1, 7100 Neusiedl")

    def test_address_sensor_missing_returns_none(self):
        """Address sensor returns None when the field is absent."""
        sensor, coordinator = self._make_sensor("address")
        coordinator.data = wrap({"geolocation": {}})
        sensor._handle_coordinator_update()
        self.assertIsNone(sensor._attr_native_value)


class TestSensorIconsAndNames(unittest.TestCase):
    """Verify icons, German display names and stable entity_id slug."""

    def _make_sensor(self, attribute, config_data=None):
        from .sensor import BlaulichtSMSEntity

        coordinator = MagicMock()
        coordinator.data = None
        coordinator.api = MagicMock()
        coordinator.api.customer_id = "cust-1"
        config = MagicMock()
        config.data = config_data or {}
        return BlaulichtSMSEntity(coordinator, attribute, config)

    def test_every_configured_attribute_has_icon_and_name(self):
        """SENSOR_ICONS and SENSOR_NAMES cover every exposed attribute."""
        from .constants import CONF_TRACK_RECIPIENT
        from .sensor import (
            DERIVED_FIELDS,
            RECIPIENT_COUNT_FIELDS,
            SENSOR_FIELDS,
            SENSOR_ICONS,
            SENSOR_NAMES,
        )

        expected = set(
            SENSOR_FIELDS + RECIPIENT_COUNT_FIELDS + DERIVED_FIELDS
        ) | {CONF_TRACK_RECIPIENT}
        self.assertTrue(expected.issubset(SENSOR_ICONS.keys()))
        self.assertTrue(expected.issubset(SENSOR_NAMES.keys()))

    def test_icon_assigned_from_mapping(self):
        """Constructor assigns _attr_icon from SENSOR_ICONS."""
        from .sensor import SENSOR_ICONS

        for attribute, icon in SENSOR_ICONS.items():
            sensor = self._make_sensor(
                attribute, config_data={attribute: "+4399"}
            )
            self.assertEqual(sensor._attr_icon, icon, attribute)

    def test_display_name_uses_german_label(self):
        """Display name embeds the German label, not the raw attribute key."""
        sensor = self._make_sensor("alarmText")
        self.assertEqual(sensor._attr_name, "BlaulichtSMS Alarmtext")

    def test_display_name_for_recipient_counts(self):
        """Recipient counts use German labels."""
        sensor_yes = self._make_sensor("recipients_yes")
        self.assertEqual(sensor_yes._attr_name, "BlaulichtSMS Empfänger Zusage")
        sensor_total = self._make_sensor("recipients_total")
        self.assertEqual(sensor_total._attr_name, "BlaulichtSMS Empfänger Gesamt")

    def test_display_name_for_tracked_recipient(self):
        """track_recipient uses the German label."""
        from .constants import CONF_TRACK_RECIPIENT

        sensor = self._make_sensor(
            CONF_TRACK_RECIPIENT, config_data={CONF_TRACK_RECIPIENT: "+4399"}
        )
        self.assertEqual(sensor._attr_name, "BlaulichtSMS Verfolgter Empfänger")

    def test_unique_id_preserves_attribute_key(self):
        """unique_id keeps the raw attribute key so existing entities survive."""
        sensor = self._make_sensor("alarmText")
        self.assertEqual(sensor._attr_unique_id, "blsms-cust-1-alarmText")

        sensor_recipients = self._make_sensor("recipients_yes")
        self.assertEqual(
            sensor_recipients._attr_unique_id, "blsms-cust-1-recipients_yes"
        )

    def test_suggested_object_id_preserves_old_slug(self):
        """suggested_object_id mirrors the pre-rename entity_id for new installs."""
        self.assertEqual(
            self._make_sensor("alarmText").suggested_object_id,
            "blaulichtsms_alarmtext",
        )
        self.assertEqual(
            self._make_sensor("recipients_yes").suggested_object_id,
            "blaulichtsms_recipients_yes",
        )
        self.assertEqual(
            self._make_sensor("customerId").suggested_object_id,
            "blaulichtsms_customerid",
        )

    def test_unknown_attribute_has_no_icon(self):
        """Attributes without a mapped icon leave _attr_icon unset."""
        sensor = self._make_sensor("authorName")
        self.assertEqual(sensor._attr_icon, "mdi:account-edit")

        sensor_unknown = self._make_sensor("nonExistent")
        self.assertFalse(getattr(sensor_unknown, "_attr_icon", None))


class TestAlarmHelpers(unittest.TestCase):
    """Pure compute helpers used by sensor entities."""

    def test_count_by_participation_empty(self):
        """Empty list yields zeroed counts."""
        from .sensor import count_by_participation

        self.assertEqual(
            count_by_participation([]),
            {"yes": 0, "no": 0, "pending": 0, "total": 0},
        )

    def test_count_by_participation_mixed(self):
        """Mixed statuses are aggregated, unknown counted only in total."""
        from .sensor import count_by_participation

        recipients = [
            {"participation": "yes"},
            {"participation": "yes"},
            {"participation": "no"},
            {"participation": "pending"},
            {"participation": "unknown"},
        ]
        self.assertEqual(
            count_by_participation(recipients),
            {"yes": 2, "no": 1, "pending": 1, "total": 5},
        )

    def test_count_by_participation_none_is_empty(self):
        """None input is treated like an empty list."""
        from .sensor import count_by_participation

        self.assertEqual(
            count_by_participation(None),
            {"yes": 0, "no": 0, "pending": 0, "total": 0},
        )

    def test_confirmed_by_function_empty(self):
        """Empty recipients list yields an empty result."""
        from .sensor import confirmed_by_function

        self.assertEqual(confirmed_by_function([]), [])

    def test_confirmed_by_function_includes_unconfirmed(self):
        """Functions present on any recipient are included, even with yes=0."""
        from .sensor import confirmed_by_function

        recipients = [
            {
                "participation": "no",
                "functions": [
                    {
                        "functionId": "F1",
                        "name": "ATS",
                        "shortForm": "ATS",
                        "order": 1,
                        "backgroundHexColorCode": "#fff",
                        "foregroundHexColorCode": "#000",
                    }
                ],
            }
        ]
        result = confirmed_by_function(recipients)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["functionId"], "F1")
        self.assertEqual(result[0]["yes"], 0)
        self.assertEqual(result[0]["no"], 1)
        self.assertEqual(result[0]["pending"], 0)
        self.assertEqual(result[0]["total"], 1)

    def test_confirmed_by_function_aggregates_and_sorts(self):
        """Array is sorted by order and accumulates yes/no/pending/total."""
        from .sensor import confirmed_by_function

        f_ats = {
            "functionId": "F1",
            "name": "ATS Träger",
            "shortForm": "ATS",
            "order": 1,
            "backgroundHexColorCode": "#ebfa57",
            "foregroundHexColorCode": "#000000",
        }
        f_tmb = {
            "functionId": "F2",
            "name": "TMB Maschinist",
            "shortForm": "TMB",
            "order": 2,
            "backgroundHexColorCode": "#5bc0de",
            "foregroundHexColorCode": "#ffffff",
        }
        recipients = [
            {"participation": "yes", "functions": [f_ats, f_tmb]},
            {"participation": "yes", "functions": [f_ats]},
            {"participation": "no", "functions": [f_ats]},
            {"participation": "pending", "functions": [f_tmb]},
            {"participation": "unknown", "functions": [f_tmb]},
        ]
        result = confirmed_by_function(recipients)
        self.assertEqual([r["shortForm"] for r in result], ["ATS", "TMB"])
        ats = result[0]
        self.assertEqual(
            {k: ats[k] for k in ("functionId", "name", "shortForm", "order",
                                 "backgroundColor", "foregroundColor",
                                 "yes", "no", "pending", "total")},
            {
                "functionId": "F1",
                "name": "ATS Träger",
                "shortForm": "ATS",
                "order": 1,
                "backgroundColor": "#ebfa57",
                "foregroundColor": "#000000",
                "yes": 2,
                "no": 1,
                "pending": 0,
                "total": 3,
            },
        )
        tmb = result[1]
        self.assertEqual(tmb["yes"], 1)
        self.assertEqual(tmb["pending"], 1)
        self.assertEqual(tmb["total"], 3)

    def test_confirmed_by_function_omits_never_seen(self):
        """Functions that never appear on any recipient are not in the result."""
        from .sensor import confirmed_by_function

        self.assertEqual(
            confirmed_by_function([{"participation": "yes", "functions": []}]), []
        )

    def test_get_address_present(self):
        """Address is returned when present under geolocation."""
        from .sensor import get_address

        alarm = {"geolocation": {"address": "Hauptplatz 1, 7100 Neusiedl"}}
        self.assertEqual(get_address(alarm), "Hauptplatz 1, 7100 Neusiedl")

    def test_get_address_none(self):
        """Missing geolocation or address yields None."""
        from .sensor import get_address

        self.assertIsNone(get_address({"geolocation": {"address": None}}))
        self.assertIsNone(get_address({"geolocation": {}}))
        self.assertIsNone(get_address({}))


if __name__ == "__main__":
    unittest.main()
