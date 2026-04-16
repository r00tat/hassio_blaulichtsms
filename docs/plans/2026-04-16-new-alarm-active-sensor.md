# New Alarm Active Sensor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `new_alarm_active` binary sensor that fires a guaranteed False→True transition whenever a fresh alarm arrives, so Home Assistant automations can trigger reliably.

**Architecture:** A new `BlaulichtSMSNewAlarmActiveSensor` class lives next to the existing `BlaulichtSMSAlarmActiveSensor` in [custom_components/blaulichtsms/binary_sensor.py](../../custom_components/blaulichtsms/binary_sensor.py). It listens to the existing `BlaulichtSMSCoordinator` (30 s poll), tracks the last-seen `alarmId`, and on a new id forces a False write before re-evaluating the target state. Target state becomes True only when `alarmDate` is within a configurable window (default 300 s) and — if `track_recipient` is set — the tracked recipient's `participation == "yes"`.

**Tech Stack:** Python 3, Home Assistant `BinarySensorEntity` + `CoordinatorEntity`, voluptuous for schema, unittest (`IsolatedAsyncioTestCase`) for tests, ruff for linting.

**Reference design:** [2026-04-16-new-alarm-active-sensor-design.md](./2026-04-16-new-alarm-active-sensor-design.md).

---

## Preconditions

- Working directory is the repo root `/Users/paul/Documents/developing/hassio/blaulichtsms`.
- Current branch is `feature/new_alarm_active_sensor` (already checked out).
- `.venv` exists. Activate with `source .venv/bin/activate` before running tests / ruff.

---

## Task 1: Add configuration constants

**Files:**
- Modify: `custom_components/blaulichtsms/constants.py`

**Step 1: Add the constants**

Append to [custom_components/blaulichtsms/constants.py](../../custom_components/blaulichtsms/constants.py) after the existing `CONF_*` / `DEFAULT_*` block:

```python
CONF_NEW_ALARM_DURATION = "new_alarm_duration"

DEFAULT_NEW_ALARM_DURATION = 300
```

Keep them grouped with the other `CONF_*` / `DEFAULT_*` constants (CONF block with the other CONF entries, DEFAULT with other DEFAULTs).

**Step 2: Verify import works**

Run: `source .venv/bin/activate && python -c "from custom_components.blaulichtsms.constants import CONF_NEW_ALARM_DURATION, DEFAULT_NEW_ALARM_DURATION; print(CONF_NEW_ALARM_DURATION, DEFAULT_NEW_ALARM_DURATION)"`

Expected: `new_alarm_duration 300`

**Step 3: Commit**

```bash
git add custom_components/blaulichtsms/constants.py
git commit -m "feat(blaulichtsms): add new_alarm_duration config constants"
```

---

## Task 2: Extend schema with new option

**Files:**
- Modify: `custom_components/blaulichtsms/schema.py`

**Step 1: Update imports**

In [custom_components/blaulichtsms/schema.py](../../custom_components/blaulichtsms/schema.py), extend the existing import from `.constants` to include:

```python
from .constants import (
    CONF_CUSTOMER_ID,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ALARM_DURATION,
    CONF_SHOW_INFOS,
    DEFAULT_ALARM_DURATION,
    DEFAULT_SHOW_INFOS,
    CONF_TRACK_RECIPIENT,
    CONF_NEW_ALARM_DURATION,
    DEFAULT_NEW_ALARM_DURATION,
)
```

**Step 2: Add field to `BLAULICHTSMS_SCHEMA`**

Insert before the `CONF_TRACK_RECIPIENT` entry:

```python
    vol.Optional(
        CONF_NEW_ALARM_DURATION,
        default=DEFAULT_NEW_ALARM_DURATION,
        description="Window (seconds) in which a freshly arrived alarm triggers new_alarm_active",
    ): cv.positive_int,
```

**Step 3: Add field to `options_schema`**

Inside the `vol.Schema({...})` in `options_schema`, before the `CONF_TRACK_RECIPIENT` entry:

```python
            vol.Optional(
                CONF_NEW_ALARM_DURATION,
                default=data.get(CONF_NEW_ALARM_DURATION, DEFAULT_NEW_ALARM_DURATION),
                description="Window (seconds) in which a freshly arrived alarm triggers new_alarm_active",
            ): cv.positive_int,
```

**Step 4: Verify**

Run: `source .venv/bin/activate && python -c "from custom_components.blaulichtsms.schema import BLAULICHTSMS_SCHEMA, options_schema; print('new_alarm_duration' in {k.schema if hasattr(k, 'schema') else k for k in BLAULICHTSMS_SCHEMA})"`

Expected: `True`

**Step 5: Commit**

```bash
git add custom_components/blaulichtsms/schema.py
git commit -m "feat(blaulichtsms): expose new_alarm_duration in config/options schemas"
```

---

## Task 3: Add translation labels

**Files:**
- Modify: `custom_components/blaulichtsms/strings.json`
- Modify: `custom_components/blaulichtsms/translations/en.json`
- Modify: `custom_components/blaulichtsms/translations/de.json`

**Step 1: Update `strings.json`**

In the `config.step.user.data` object of [custom_components/blaulichtsms/strings.json](../../custom_components/blaulichtsms/strings.json), add a `new_alarm_duration` key. The existing file has no `options` section; leave it as-is.

Add key (match existing indentation):

```json
"new_alarm_duration": "New alarm window (seconds)"
```

Place it right after `"alarm_duration": ...` for readability.

**Step 2: Update `translations/en.json`**

Add the same key in both `config.step.user.data` and `options.step.init.data` blocks:

```json
"new_alarm_duration": "New alarm window (seconds)"
```

**Step 3: Update `translations/de.json`**

Add the German label in both `config.step.user.data` and `options.step.init.data`:

```json
"new_alarm_duration": "Zeitfenster für neuen Alarm (Sekunden)"
```

**Step 4: Validate JSON**

Run: `python -m json.tool custom_components/blaulichtsms/strings.json > /dev/null && python -m json.tool custom_components/blaulichtsms/translations/en.json > /dev/null && python -m json.tool custom_components/blaulichtsms/translations/de.json > /dev/null && echo OK`

Expected: `OK`

**Step 5: Commit**

```bash
git add custom_components/blaulichtsms/strings.json custom_components/blaulichtsms/translations/
git commit -m "feat(blaulichtsms): add translation labels for new_alarm_duration"
```

---

## Task 4: Write failing unit tests for the sensor decision logic

**Context:** The existing `test_blaulichtsms.py` uses `unittest.IsolatedAsyncioTestCase` and hits the live API (gated by `SKIP_INTEGRATION_TEST`). The new sensor logic must be testable **without** Home Assistant, so we will structure the sensor so that the pure decision function `_evaluate_target` takes an alarm dict + "now" and returns a bool. We'll test that + the transition logic via a lightweight fake coordinator.

**Files:**
- Modify: `custom_components/blaulichtsms/test_blaulichtsms.py`

**Step 1: Add a new test class at the bottom of the file**

Append to [custom_components/blaulichtsms/test_blaulichtsms.py](../../custom_components/blaulichtsms/test_blaulichtsms.py) (before the `if __name__ == "__main__":` block):

```python
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch


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
        sensor, _ = self._make_sensor()
        alarm = _make_alarm(minutes_ago=1)
        self.assertTrue(sensor._evaluate_target(alarm))

    def test_evaluate_target_outside_window_no_track(self):
        sensor, _ = self._make_sensor()
        alarm = _make_alarm(minutes_ago=10)
        self.assertFalse(sensor._evaluate_target(alarm))

    def test_evaluate_target_track_recipient_yes(self):
        sensor, _ = self._make_sensor(track_recipient="+4312345")
        alarm = _make_alarm(
            minutes_ago=1,
            recipients=[{"msisdn": "+4312345", "participation": "yes"}],
        )
        self.assertTrue(sensor._evaluate_target(alarm))

    def test_evaluate_target_track_recipient_no_confirmation(self):
        sensor, _ = self._make_sensor(track_recipient="+4312345")
        alarm = _make_alarm(
            minutes_ago=1,
            recipients=[{"msisdn": "+4312345", "participation": "no"}],
        )
        self.assertFalse(sensor._evaluate_target(alarm))

    def test_evaluate_target_track_recipient_missing(self):
        sensor, _ = self._make_sensor(track_recipient="+4312345")
        alarm = _make_alarm(minutes_ago=1, recipients=[])
        self.assertFalse(sensor._evaluate_target(alarm))

    def test_evaluate_target_track_recipient_yes_but_expired(self):
        sensor, _ = self._make_sensor(track_recipient="+4312345")
        alarm = _make_alarm(
            minutes_ago=10,
            recipients=[{"msisdn": "+4312345", "participation": "yes"}],
        )
        self.assertFalse(sensor._evaluate_target(alarm))

    def test_new_alarm_forces_false_then_true(self):
        sensor, coordinator = self._make_sensor()
        # Simulate prior state: was True from a previous alarm
        sensor._attr_is_on = True
        sensor._last_alarm_id = "OLD"
        coordinator.data = _make_alarm(alarm_id="NEW", minutes_ago=1)

        sensor._handle_coordinator_update()

        calls = sensor.async_write_ha_state.call_args_list
        # Expect two writes: first with is_on False, second with is_on True.
        self.assertEqual(len(calls), 2)
        # We inspect the is_on value captured at each call time.
        # Since async_write_ha_state is called synchronously inside _handle_coordinator_update,
        # we capture is_on via side_effect in a dedicated test below.
        self.assertTrue(sensor._attr_is_on)
        self.assertEqual(sensor._last_alarm_id, "NEW")

    def test_new_alarm_writes_false_before_true(self):
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
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = True
        sensor._last_alarm_id = "SAME"
        coordinator.data = _make_alarm(alarm_id="SAME", minutes_ago=1)

        sensor._handle_coordinator_update()

        # No state change: no write.
        sensor.async_write_ha_state.assert_not_called()
        self.assertTrue(sensor._attr_is_on)

    def test_new_alarm_outside_window_stays_false(self):
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = False
        sensor._last_alarm_id = None
        coordinator.data = _make_alarm(alarm_id="NEW", minutes_ago=10)

        captured = []
        sensor.async_write_ha_state = MagicMock(
            side_effect=lambda: captured.append(sensor._attr_is_on)
        )

        sensor._handle_coordinator_update()

        # One forced False write on new-alarm detection; no flip to True.
        self.assertEqual(captured, [False])
        self.assertFalse(sensor._attr_is_on)

    def test_late_confirmation_flips_to_true(self):
        sensor, coordinator = self._make_sensor(track_recipient="+4312345")
        # Initial poll: alarm present, no confirmation yet.
        coordinator.data = _make_alarm(
            alarm_id="NEW",
            minutes_ago=1,
            recipients=[{"msisdn": "+4312345", "participation": "pending"}],
        )
        sensor._handle_coordinator_update()
        self.assertFalse(sensor._attr_is_on)

        # Next poll: same alarm, now confirmed.
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
        sensor, coordinator = self._make_sensor()
        sensor._attr_is_on = True
        coordinator.data = None

        sensor._handle_coordinator_update()

        self.assertFalse(sensor._attr_is_on)
        sensor.async_write_ha_state.assert_called_once()
```

**Step 2: Run tests to see them fail**

Run: `source .venv/bin/activate && SKIP_INTEGRATION_TEST=1 python -m unittest custom_components.blaulichtsms.test_blaulichtsms -v 2>&1 | tail -40`

Expected: Failures/errors on every `TestNewAlarmActiveSensor.*` test with an `ImportError` like `cannot import name 'BlaulichtSMSNewAlarmActiveSensor'`.

**Step 3: Commit (failing tests)**

```bash
git add custom_components/blaulichtsms/test_blaulichtsms.py
git commit -m "test(blaulichtsms): add failing tests for new_alarm_active sensor"
```

---

## Task 5: Implement `BlaulichtSMSNewAlarmActiveSensor`

**Files:**
- Modify: `custom_components/blaulichtsms/binary_sensor.py`

**Step 1: Extend imports**

In [custom_components/blaulichtsms/binary_sensor.py](../../custom_components/blaulichtsms/binary_sensor.py), extend the import block from `.constants`:

```python
from .constants import (
    DOMAIN,
    CONF_CUSTOMER_ID,
    CONF_ALARM_DURATION,
    CONF_NEW_ALARM_DURATION,
    CONF_TRACK_RECIPIENT,
    DEFAULT_ALARM_DURATION,
    DEFAULT_NEW_ALARM_DURATION,
    VERSION,
)
```

**Step 2: Add the new sensor class**

Append this class at the end of [custom_components/blaulichtsms/binary_sensor.py](../../custom_components/blaulichtsms/binary_sensor.py), after `BlaulichtSMSAlarmActiveSensor`:

```python
class BlaulichtSMSNewAlarmActiveSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor that fires False→True whenever a fresh alarm arrives."""

    def __init__(
        self,
        coordinator: BlaulichtSMSCoordinator,
        hass: HomeAssistant,
        new_alarm_duration: int,
        track_recipient: str | None,
    ) -> None:
        """Create the sensor."""
        super().__init__(coordinator, context="new-alarm-active")
        self.hass = hass
        self.coordinator = coordinator
        self.blaulichtsms = self.coordinator.api
        self._new_alarm_duration = new_alarm_duration
        self._track_recipient = track_recipient or None
        self._last_alarm_id = None
        self._attr_name = "BlaulichtSMS New Alarm Active"
        self._attr_unique_id = (
            f"blsms-{self.blaulichtsms.customer_id}-new-alarm-active"
        )
        self._attr_is_on = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """React to a new coordinator poll."""
        data = self.coordinator.data
        if not data:
            if self._attr_is_on:
                self._attr_is_on = False
                self.async_write_ha_state()
            return

        alarm_id = data.get("alarmId")
        if alarm_id != self._last_alarm_id:
            self._last_alarm_id = alarm_id
            self._attr_is_on = False
            self.async_write_ha_state()

        target = self._evaluate_target(data)
        if self._attr_is_on != target:
            self._attr_is_on = target
            self.async_write_ha_state()

    def _evaluate_target(self, data: dict) -> bool:
        """Return the intended is_on value for the given alarm payload."""
        alarm_date_raw = data.get("alarmDate")
        if not alarm_date_raw:
            return False
        alarm_date = datetime.fromisoformat(alarm_date_raw)
        within_window = datetime.now(alarm_date.tzinfo) < alarm_date + timedelta(
            seconds=self._new_alarm_duration
        )
        if not within_window:
            return False

        if self._track_recipient:
            recipient = next(
                (
                    r
                    for r in data.get("recipients", [])
                    if r.get("msisdn") == self._track_recipient
                ),
                None,
            )
            return bool(recipient and recipient.get("participation") == "yes")
        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.blaulichtsms.customer_id)},
            name=f"BlaulichtSMS {self.blaulichtsms.customer_id}",
            manufacturer="BlaulichtSMS",
            model="API",
            sw_version=VERSION,
        )
```

**Step 3: Run tests to see them pass**

Run: `source .venv/bin/activate && SKIP_INTEGRATION_TEST=1 python -m unittest custom_components.blaulichtsms.test_blaulichtsms.TestNewAlarmActiveSensor -v 2>&1 | tail -30`

Expected: all `TestNewAlarmActiveSensor.*` tests pass (`OK`). If any test fails, read the failure — do **not** change the test expectations; fix the implementation.

**Step 4: Commit**

```bash
git add custom_components/blaulichtsms/binary_sensor.py
git commit -m "feat(blaulichtsms): implement new_alarm_active binary sensor"
```

---

## Task 6: Register the sensor in platform setup

**Files:**
- Modify: `custom_components/blaulichtsms/binary_sensor.py` (function `setup_blaulichtsms`)

**Step 1: Add the new entity to the entity list**

In `setup_blaulichtsms` inside [custom_components/blaulichtsms/binary_sensor.py](../../custom_components/blaulichtsms/binary_sensor.py), replace the `entities = [...]` block with:

```python
    entities = [
        BlaulichtSMSAlarmActiveSensor(
            coordinator,
            hass,
            config.data.get(CONF_ALARM_DURATION, DEFAULT_ALARM_DURATION),
        ),
        BlaulichtSMSNewAlarmActiveSensor(
            coordinator,
            hass,
            config.data.get(CONF_NEW_ALARM_DURATION, DEFAULT_NEW_ALARM_DURATION),
            config.data.get(CONF_TRACK_RECIPIENT),
        ),
    ]
```

**Step 2: Run the full unit test suite**

Run: `source .venv/bin/activate && SKIP_INTEGRATION_TEST=1 python -m unittest custom_components.blaulichtsms.test_blaulichtsms -v 2>&1 | tail -30`

Expected: all tests pass, including the original (non-integration) ones.

**Step 3: Run ruff**

Run: `source .venv/bin/activate && ruff check custom_components/blaulichtsms/`

Expected: `All checks passed!` (or no new errors vs. baseline). Fix any new warnings before continuing — do not add `# noqa` suppressions.

**Step 4: Commit**

```bash
git add custom_components/blaulichtsms/binary_sensor.py
git commit -m "feat(blaulichtsms): register new_alarm_active sensor on setup"
```

---

## Task 7: Manual smoke test in Home Assistant (optional but recommended)

**Context:** The tests cover the decision logic but not the HA wiring. A quick manual check confirms the sensor shows up and reacts.

**Step 1: Rsync the component into the local HA docker config and restart**

Run: `./dev.sh`

Expected: the `homeassistant` docker container starts/restarts and tails logs.

**Step 2: Verify the entity exists**

In the HA UI (http://localhost:8123), go to **Developer Tools → States** and search for `binary_sensor.blaulichtsms_new_alarm_active`.

Expected: entity present, state `off` when no fresh alarm.

**Step 3: Verify config option appears**

In **Settings → Devices & Services → Blaulicht SMS → Configure**, verify the **New alarm window (seconds)** field is shown and defaults to `300`.

**Step 4: If everything looks right, no additional commit required.**

If a bug shows up, fix it, add a regression test, re-run Task 5 Step 3 and Task 6 Step 2, commit.

---

## Done criteria

- `new_alarm_active` binary sensor listed in HA, default `off`.
- On a fresh alarm with `alarmDate` inside the configured window: sensor emits one `off` write followed by an `on` write in the same coordinator cycle (when no `track_recipient`), or emits `off` on detection and flips to `on` when the tracked recipient confirms (when `track_recipient` is set).
- Outside the window, sensor stays `off`.
- All unit tests pass with `SKIP_INTEGRATION_TEST=1`.
- `ruff check custom_components/blaulichtsms/` is clean.
- All commits on `feature/new_alarm_active_sensor`.
