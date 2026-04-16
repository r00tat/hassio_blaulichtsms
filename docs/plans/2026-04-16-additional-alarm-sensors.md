# Additional Alarm Sensors Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose additional fields from the BlaulichtSMS Dashboard API as Home Assistant entities so automations and dashboards can react to recipient counts, function-level confirmations, reply-requirement, and the event address.

**Architecture:** Keep the existing generic `BlaulichtSMSEntity` dispatcher in [sensor.py](../../custom_components/blaulichtsms/sensor.py) — add new "synthetic" attribute names (`recipients_yes`, `recipients_no`, `recipients_pending`, `recipients_total`, `confirmed_by_function`, `address`) that are computed from the raw alarm dict via pure module-level functions. Add a new `BlaulichtSMSNeedsAcknowledgementSensor` binary sensor alongside the existing ones in [binary_sensor.py](../../custom_components/blaulichtsms/binary_sensor.py). Pure compute functions live in sensor.py module scope so they can be unit-tested directly without Home Assistant.

**Tech Stack:** Python 3.10, Home Assistant custom component framework, unittest.

**API reference (verified against live payload 2026-04-16):**
- `alarm.recipients[].participation` ∈ `{yes, no, pending, unknown}`
- `alarm.recipients[].functions[]` has `functionId`, `name`, `shortForm`, `order`, `backgroundHexColorCode`, `foregroundHexColorCode`
- `alarm.needsAcknowledgement` is a bool
- `alarm.geolocation.address` is a string-or-null
- `alarm.coordinates.lat/lon` exists at top level (kept for backward compat)

**Known pre-existing bug (out of scope):** [binary_sensor.py:73-81](../../custom_components/blaulichtsms/binary_sensor.py#L73-L81) instantiates `BlaulichtSMSNewAlarmActiveSensor` twice (once correctly, once with a legacy 4-arg signature that will crash). Do not fix in this plan — file it as a separate change.

---

## Task 1: Pure helper functions + tests

**Files:**
- Modify: `custom_components/blaulichtsms/sensor.py` (add module-level helpers)
- Modify: `custom_components/blaulichtsms/test_blaulichtsms.py` (add `TestAlarmHelpers`)

**Step 1.1: Write the failing tests**

Append to [test_blaulichtsms.py](../../custom_components/blaulichtsms/test_blaulichtsms.py) (before the `if __name__ == "__main__":` guard):

```python
class TestAlarmHelpers(unittest.TestCase):
    """Pure compute helpers used by sensor entities."""

    def test_count_by_participation_empty(self):
        from .sensor import count_by_participation

        self.assertEqual(
            count_by_participation([]),
            {"yes": 0, "no": 0, "pending": 0, "total": 0},
        )

    def test_count_by_participation_mixed(self):
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
        from .sensor import count_by_participation

        self.assertEqual(
            count_by_participation(None),
            {"yes": 0, "no": 0, "pending": 0, "total": 0},
        )

    def test_confirmed_by_function_empty(self):
        from .sensor import confirmed_by_function

        self.assertEqual(confirmed_by_function([]), [])

    def test_confirmed_by_function_no_confirmations(self):
        """Recipients without participation=yes yield no function entries."""
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
        self.assertEqual(confirmed_by_function(recipients), [])

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

        self.assertEqual(confirmed_by_function([{"participation": "yes", "functions": []}]), [])

    def test_get_address_present(self):
        from .sensor import get_address

        alarm = {"geolocation": {"address": "Hauptplatz 1, 7100 Neusiedl"}}
        self.assertEqual(get_address(alarm), "Hauptplatz 1, 7100 Neusiedl")

    def test_get_address_none(self):
        from .sensor import get_address

        self.assertIsNone(get_address({"geolocation": {"address": None}}))
        self.assertIsNone(get_address({"geolocation": {}}))
        self.assertIsNone(get_address({}))
```

**Step 1.2: Run tests and confirm they fail**

Run: `SKIP_INTEGRATION_TEST=1 uv run python -m unittest custom_components.blaulichtsms.test_blaulichtsms.TestAlarmHelpers -v`
Expected: `ImportError` / `AttributeError` — functions do not exist yet.

**Step 1.3: Implement helpers**

Add to [sensor.py](../../custom_components/blaulichtsms/sensor.py) near the top, below imports and before `SENSOR_FIELDS`:

```python
def count_by_participation(recipients: list[dict] | None) -> dict[str, int]:
    """Count recipients by participation status.

    Returns a dict with keys yes/no/pending/total. Unknown statuses are counted
    only in total, so yes+no+pending <= total.
    """
    counts = {"yes": 0, "no": 0, "pending": 0, "total": 0}
    for r in recipients or []:
        counts["total"] += 1
        status = r.get("participation")
        if status in counts:
            counts[status] += 1
    return counts


def confirmed_by_function(recipients: list[dict] | None) -> list[dict]:
    """Aggregate recipients per function, keeping only functions actually seen.

    Returned list is sorted by each function's `order` field. Each entry carries
    the function metadata (id, name, shortForm, colors) plus yes/no/pending/total
    counts of recipients holding that function.
    """
    buckets: dict[str, dict] = {}
    for recipient in recipients or []:
        status = recipient.get("participation")
        for fn in recipient.get("functions") or []:
            fn_id = fn.get("functionId")
            if fn_id is None:
                continue
            entry = buckets.get(fn_id)
            if entry is None:
                entry = {
                    "functionId": fn_id,
                    "name": fn.get("name"),
                    "shortForm": fn.get("shortForm"),
                    "order": fn.get("order", 0),
                    "backgroundColor": fn.get("backgroundHexColorCode"),
                    "foregroundColor": fn.get("foregroundHexColorCode"),
                    "yes": 0,
                    "no": 0,
                    "pending": 0,
                    "total": 0,
                }
                buckets[fn_id] = entry
            entry["total"] += 1
            if status in ("yes", "no", "pending"):
                entry[status] += 1
    return sorted(buckets.values(), key=lambda e: (e["order"], e["shortForm"] or ""))


def get_address(alarm: dict | None) -> str | None:
    """Return the street address from alarm.geolocation.address, or None."""
    if not alarm:
        return None
    geo = alarm.get("geolocation") or {}
    return geo.get("address")
```

**Step 1.4: Run tests and confirm they pass**

Run: `SKIP_INTEGRATION_TEST=1 uv run python -m unittest custom_components.blaulichtsms.test_blaulichtsms.TestAlarmHelpers -v`
Expected: all 9 tests pass.

**Step 1.5: Run ruff**

Run: `uv run python -m ruff check custom_components/blaulichtsms/sensor.py custom_components/blaulichtsms/test_blaulichtsms.py`
Expected: no errors. Fix any if reported.

**Step 1.6: Commit**

```bash
git add custom_components/blaulichtsms/sensor.py custom_components/blaulichtsms/test_blaulichtsms.py
git commit -m "feat(blaulichtsms): add pure helpers for recipient and function aggregates"
```

---

## Task 2: Recipient count sensors

**Files:**
- Modify: `custom_components/blaulichtsms/sensor.py`
- Modify: `custom_components/blaulichtsms/test_blaulichtsms.py`

**Step 2.1: Write failing test**

Append to `TestSensorEntity` in [test_blaulichtsms.py](../../custom_components/blaulichtsms/test_blaulichtsms.py):

```python
    def test_recipients_yes_count(self):
        """recipients_yes sensor counts participation=='yes'."""
        sensor, coordinator = self._make_sensor("recipients_yes")
        coordinator.data = _wrap(
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
        coordinator.data = _wrap({"recipients": [{"participation": "yes"}] * 3})
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
        coord_no.data = _wrap({"recipients": recipients})
        sensor_no._handle_coordinator_update()
        self.assertEqual(sensor_no._attr_native_value, 2)

        sensor_pending, coord_p = self._make_sensor("recipients_pending")
        coord_p.data = _wrap({"recipients": recipients})
        sensor_pending._handle_coordinator_update()
        self.assertEqual(sensor_pending._attr_native_value, 1)
```

**Step 2.2: Run test, confirm failure**

Run: `SKIP_INTEGRATION_TEST=1 uv run python -m unittest custom_components.blaulichtsms.test_blaulichtsms.TestSensorEntity -v`
Expected: 3 new tests fail (native_value ends up None or raises).

**Step 2.3: Implement recipient count dispatch**

In [sensor.py](../../custom_components/blaulichtsms/sensor.py):

1. Add the synthetic names to a new constant alongside `SENSOR_FIELDS`:

```python
RECIPIENT_COUNT_FIELDS = [
    "recipients_yes",
    "recipients_no",
    "recipients_pending",
    "recipients_total",
]
```

2. In `setup_blaulichtsms`, extend the entity list:

```python
    entities = [
        BlaulichtSMSEntity(coordinator, attribute, config)
        for attribute in SENSOR_FIELDS + RECIPIENT_COUNT_FIELDS
    ]
```

3. In `BlaulichtSMSEntity.update_state_from_coordinator`, add a branch **before** the existing `if self.attribute == "recipients":` branch (which is dead code — leave it for now, will remove in task 3 cleanup):

```python
        if self.attribute.startswith("recipients_"):
            key = self.attribute.removeprefix("recipients_")
            self._attr_native_value = count_by_participation(
                alarm.get("recipients")
            )[key]
            return
```

Note the early `return` — these are scalar sensors and need no further processing.

**Step 2.4: Run tests, confirm pass**

Run: `SKIP_INTEGRATION_TEST=1 uv run python -m unittest custom_components.blaulichtsms.test_blaulichtsms.TestSensorEntity -v`
Expected: all tests in `TestSensorEntity` pass.

**Step 2.5: Run ruff**

Run: `uv run python -m ruff check custom_components/blaulichtsms/sensor.py`

**Step 2.6: Commit**

```bash
git add custom_components/blaulichtsms/sensor.py custom_components/blaulichtsms/test_blaulichtsms.py
git commit -m "feat(blaulichtsms): expose recipients_yes/no/pending/total sensors"
```

---

## Task 3: `confirmed_by_function` sensor

**Files:**
- Modify: `custom_components/blaulichtsms/sensor.py`
- Modify: `custom_components/blaulichtsms/test_blaulichtsms.py`

**Step 3.1: Write failing test**

Append to `TestSensorEntity`:

```python
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
        coordinator.data = _wrap(
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
        coordinator.data = _wrap({"recipients": []})
        sensor._handle_coordinator_update()
        self.assertEqual(sensor._attr_native_value, 0)
        self.assertEqual(sensor._attr_extra_state_attributes["functions"], [])
```

**Step 3.2: Run test, confirm failure**

Run: `SKIP_INTEGRATION_TEST=1 uv run python -m unittest custom_components.blaulichtsms.test_blaulichtsms.TestSensorEntity -v`
Expected: 2 new tests fail.

**Step 3.3: Implement**

In [sensor.py](../../custom_components/blaulichtsms/sensor.py):

1. Add a third synthetic list:

```python
DERIVED_FIELDS = [
    "confirmed_by_function",
    "address",
]
```

2. Extend entity creation:

```python
    entities = [
        BlaulichtSMSEntity(coordinator, attribute, config)
        for attribute in SENSOR_FIELDS + RECIPIENT_COUNT_FIELDS + DERIVED_FIELDS
    ]
```

3. Add branches in `update_state_from_coordinator` (after the `recipients_*` branch, before the existing `if self.attribute == "recipients":` branch):

```python
        if self.attribute == "confirmed_by_function":
            functions = confirmed_by_function(alarm.get("recipients"))
            self._attr_native_value = len(functions)
            self._attr_extra_state_attributes = {"functions": functions}
            return

        if self.attribute == "address":
            self._attr_native_value = get_address(alarm)
            return
```

4. Also: remove the dead `if self.attribute == "recipients":` branch from `update_state_from_coordinator` — nothing ever sets `self.attribute` to the bare string `recipients`, and the new `recipients_*` branch handles the real use case.

**Step 3.4: Run tests, confirm pass**

Run: `SKIP_INTEGRATION_TEST=1 uv run python -m unittest custom_components.blaulichtsms.test_blaulichtsms.TestSensorEntity -v`
Expected: all pass.

**Step 3.5: Add address coverage**

Append to `TestSensorEntity`:

```python
    def test_address_sensor(self):
        """address sensor returns geolocation.address or None."""
        sensor, coordinator = self._make_sensor("address")
        coordinator.data = _wrap(
            {"geolocation": {"address": "Hauptplatz 1, 7100 Neusiedl"}}
        )
        sensor._handle_coordinator_update()
        self.assertEqual(sensor._attr_native_value, "Hauptplatz 1, 7100 Neusiedl")

    def test_address_sensor_missing_returns_none(self):
        """address sensor returns None when the field is absent."""
        sensor, coordinator = self._make_sensor("address")
        coordinator.data = _wrap({"geolocation": {}})
        sensor._handle_coordinator_update()
        self.assertIsNone(sensor._attr_native_value)
```

**Step 3.6: Run all sensor tests**

Run: `SKIP_INTEGRATION_TEST=1 uv run python -m unittest custom_components.blaulichtsms.test_blaulichtsms.TestSensorEntity custom_components.blaulichtsms.test_blaulichtsms.TestAlarmHelpers -v`
Expected: all pass.

**Step 3.7: Run ruff**

Run: `uv run python -m ruff check custom_components/blaulichtsms/sensor.py`

**Step 3.8: Commit**

```bash
git add custom_components/blaulichtsms/sensor.py custom_components/blaulichtsms/test_blaulichtsms.py
git commit -m "feat(blaulichtsms): add confirmed_by_function and address sensors"
```

---

## Task 4: `needs_acknowledgement` binary sensor

**Files:**
- Modify: `custom_components/blaulichtsms/binary_sensor.py`
- Modify: `custom_components/blaulichtsms/test_blaulichtsms.py`

**Step 4.1: Write failing test**

Append to [test_blaulichtsms.py](../../custom_components/blaulichtsms/test_blaulichtsms.py), as a new test class:

```python
class TestNeedsAcknowledgementSensor(unittest.TestCase):
    """Tests for BlaulichtSMSNeedsAcknowledgementSensor."""

    def _make_sensor(self):
        from .binary_sensor import BlaulichtSMSNeedsAcknowledgementSensor

        coordinator = MagicMock()
        coordinator.data = None
        coordinator.api = MagicMock()
        coordinator.api.customer_id = "cust-1"
        sensor = BlaulichtSMSNeedsAcknowledgementSensor(coordinator)
        sensor.async_write_ha_state = MagicMock()
        return sensor, coordinator

    def test_off_when_no_data(self):
        sensor, coordinator = self._make_sensor()
        coordinator.data = None
        sensor._handle_coordinator_update()
        self.assertFalse(sensor._attr_is_on)

    def test_off_when_no_alarm(self):
        sensor, coordinator = self._make_sensor()
        coordinator.data = {"alarm": None, "is_active": False}
        sensor._handle_coordinator_update()
        self.assertFalse(sensor._attr_is_on)

    def test_on_when_needs_acknowledgement_true(self):
        sensor, coordinator = self._make_sensor()
        coordinator.data = {
            "alarm": {"alarmId": "A", "needsAcknowledgement": True},
            "is_active": True,
        }
        sensor._handle_coordinator_update()
        self.assertTrue(sensor._attr_is_on)

    def test_off_when_needs_acknowledgement_false(self):
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
```

**Step 4.2: Run test, confirm failure**

Run: `SKIP_INTEGRATION_TEST=1 uv run python -m unittest custom_components.blaulichtsms.test_blaulichtsms.TestNeedsAcknowledgementSensor -v`
Expected: `ImportError` — class does not exist.

**Step 4.3: Implement sensor class**

In [binary_sensor.py](../../custom_components/blaulichtsms/binary_sensor.py), add a new class after `BlaulichtSMSAlarmActiveSensor`:

```python
class BlaulichtSMSNeedsAcknowledgementSensor(_BlaulichtSMSBinarySensorBase):
    """Binary sensor indicating whether the current alarm needs acknowledgement."""

    def __init__(self, coordinator: BlaulichtSMSCoordinator) -> None:
        """Create the sensor."""
        super().__init__(coordinator, context="needs-acknowledgement")
        customer_id = coordinator.api.customer_id
        self._attr_name = "BlaulichtSMS Needs Acknowledgement"
        self._attr_unique_id = f"blsms-{customer_id}-needs-acknowledgement"
        self._attr_is_on = self._derive_is_on()

    def _derive_is_on(self) -> bool:
        data = self.coordinator.data
        alarm = data.get("alarm") if data else None
        return bool(alarm and alarm.get("needsAcknowledgement"))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self._derive_is_on()
        self.async_write_ha_state()
```

**Step 4.4: Register the sensor**

In the `entities = [...]` list inside `setup_blaulichtsms` in [binary_sensor.py](../../custom_components/blaulichtsms/binary_sensor.py), add `BlaulichtSMSNeedsAcknowledgementSensor(coordinator)`. Do **not** touch the existing duplicate `BlaulichtSMSNewAlarmActiveSensor` lines (separate issue, flagged above).

**Step 4.5: Run test, confirm pass**

Run: `SKIP_INTEGRATION_TEST=1 uv run python -m unittest custom_components.blaulichtsms.test_blaulichtsms.TestNeedsAcknowledgementSensor -v`
Expected: all 5 tests pass.

**Step 4.6: Run ruff**

Run: `uv run python -m ruff check custom_components/blaulichtsms/binary_sensor.py custom_components/blaulichtsms/test_blaulichtsms.py`

**Step 4.7: Commit**

```bash
git add custom_components/blaulichtsms/binary_sensor.py custom_components/blaulichtsms/test_blaulichtsms.py
git commit -m "feat(blaulichtsms): add needs_acknowledgement binary sensor"
```

---

## Task 5: Full verification & manual smoke test

**Step 5.1: Full test suite (offline)**

Run: `SKIP_INTEGRATION_TEST=1 uv run python -m unittest discover -v`
Expected: all tests pass, no failures or errors. Note the total count compared to the pre-change baseline — should have grown by the new tests.

**Step 5.2: Ruff across the whole integration**

Run: `uv run python -m ruff check custom_components/blaulichtsms/`
Expected: no errors.

**Step 5.3: Live integration test (optional, requires credentials)**

If the developer has `BLAULICHTSMS_*` env vars configured via direnv:

Run: `direnv exec . uv run python -m unittest custom_components.blaulichtsms.test_blaulichtsms.TestBlaulichtsms -v`
Expected: all 3 tests pass.

**Step 5.4: Smoke test in Home Assistant (optional)**

Run: `./dev.sh`
- Wait for HA to start on port 8123.
- Open the BlaulichtSMS device page.
- Verify the new entities appear:
  - `sensor.blaulichtsms_recipients_yes` / `_no` / `_pending` / `_total`
  - `sensor.blaulichtsms_confirmed_by_function` with a populated `functions` attribute
  - `sensor.blaulichtsms_address`
  - `binary_sensor.blaulichtsms_needs_acknowledgement`
- If there is a recent alarm, check the values match what the dashboard shows.

**Step 5.5: Final commit if any cleanup**

If any follow-up fixes were made during smoke testing, commit them separately.

---

## Out of scope (follow-ups to file as separate issues)

- Duplicate instantiation of `BlaulichtSMSNewAlarmActiveSensor` in [binary_sensor.py:73-81](../../custom_components/blaulichtsms/binary_sensor.py#L73-L81) (existing bug, unrelated).
- `geolocation.radius` / `distance` / `duration` sensors — all null in current tenant, add later if a real alarm populates them.
- `productType`, `scenarioId`, `indexNumber` — low value, defer unless requested.
