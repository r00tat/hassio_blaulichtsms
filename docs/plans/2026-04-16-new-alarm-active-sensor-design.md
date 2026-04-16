# New Alarm Active Binary Sensor — Design

## Goal

Add a second binary sensor `new_alarm_active` to the BlaulichtSMS integration. It distinguishes **a fresh alarm worth triggering automations on** from the existing long-duration `alarm_active` sensor.

The sensor must always transition **False → True** when activating, even if the previous alarm's sensor was already True. This guarantees Home Assistant automations with an `off → on` trigger fire for every new alarm.

## Behavior

### State evaluation (per coordinator poll)

1. Read current alarm from coordinator.
2. If `alarmId` differs from the last seen id → **new alarm detected**:
   - Set `is_on = False` and write state (forced reset, fires `state_changed` even if previous was True).
   - Store new `alarmId`.
3. Compute target state:
   - Alarm must be within the configured new-alarm window: `now < alarmDate + new_alarm_duration`. Otherwise target is False.
   - If `track_recipient` is configured: target is True only when the tracked recipient's `participation == "yes"`. Missing recipient is treated as no confirmation.
   - Otherwise: target is True within the window.
4. If target differs from current `is_on` → update and write state.

### Transitions
- Fresh alarm, no `track_recipient`: False (reset) → True (same cycle).
- Fresh alarm, `track_recipient` set, no confirmation yet: False → stays False; flips to True on the poll where `participation=yes` arrives.
- Alarm older than window: stays False.
- Recipient confirmation arriving after window expiry: stays False (window is authoritative).

## Configuration

New option `new_alarm_duration` (seconds, default `300`).

- Added to `BLAULICHTSMS_SCHEMA` (initial setup) and `options_schema` (options flow) in [schema.py](../../custom_components/blaulichtsms/schema.py).
- Constants `CONF_NEW_ALARM_DURATION` and `DEFAULT_NEW_ALARM_DURATION` in [constants.py](../../custom_components/blaulichtsms/constants.py).
- Label in [strings.json](../../custom_components/blaulichtsms/strings.json) and translations.

## Implementation sketch

New class `BlaulichtSMSNewAlarmActiveSensor` in [binary_sensor.py](../../custom_components/blaulichtsms/binary_sensor.py).

```python
class BlaulichtSMSNewAlarmActiveSensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, hass, new_alarm_duration, track_recipient):
        super().__init__(coordinator, context="new-alarm-active")
        self._new_alarm_duration = new_alarm_duration
        self._track_recipient = track_recipient
        self._last_alarm_id = None
        self._attr_is_on = False
        self._attr_name = "BlaulichtSMS New Alarm Active"
        self._attr_unique_id = f"blsms-{...}-new-alarm-active"

    @callback
    def _handle_coordinator_update(self):
        data = self.coordinator.data
        if not data:
            if self._attr_is_on:
                self._attr_is_on = False
                self.async_write_ha_state()
            return

        alarm_id = data.get("alarmId")
        if alarm_id != self._last_alarm_id:
            self._last_alarm_id = alarm_id
            if self._attr_is_on:
                self._attr_is_on = False
            self.async_write_ha_state()  # forced False event

        target = self._evaluate_target(data)
        if self._attr_is_on != target:
            self._attr_is_on = target
            self.async_write_ha_state()

    def _evaluate_target(self, data) -> bool:
        alarm_date = datetime.fromisoformat(data["alarmDate"])
        within = datetime.now(alarm_date.tzinfo) < alarm_date + timedelta(
            seconds=self._new_alarm_duration
        )
        if not within:
            return False
        if self._track_recipient:
            recipient = next(
                (r for r in data.get("recipients", [])
                 if r.get("msisdn") == self._track_recipient),
                None,
            )
            return bool(recipient and recipient.get("participation") == "yes")
        return True
```

Register alongside the existing sensor in `setup_blaulichtsms`.

## Edge cases

| Case | Behavior |
|---|---|
| Coordinator has no data | False (no-op if already False) |
| Integration startup, alarm already > 5 min old | Treated as "new" (id changes from `None`), write False, window check fails → stays False. No spurious trigger. |
| Two new alarms in rapid succession | Each triggers its own False→True sequence. |
| `participation` flips from `yes` back to something else within window | Sensor flips True → False (rare, but consistent with re-evaluation). |
| `track_recipient` configured but recipient not in `recipients` list | Treated as no confirmation → False. |

## Testing

Extend [test_blaulichtsms.py](../../custom_components/blaulichtsms/test_blaulichtsms.py) with unit tests for `_evaluate_target` and the full update cycle:

- New alarm within window, no `track_recipient` → False, then True.
- New alarm older than window → stays False.
- New alarm within window, `track_recipient` set, no confirmation → False; after confirmation → True.
- Confirmation arriving after window → stays False.
- Same alarm id across polls, within window → no extra False write.
- Transition from True (old alarm) to new alarm id → False event emitted, then True.

## Files touched

- [constants.py](../../custom_components/blaulichtsms/constants.py) — new config constants
- [schema.py](../../custom_components/blaulichtsms/schema.py) — schema entries for both flows
- [strings.json](../../custom_components/blaulichtsms/strings.json) — label for new option
- [translations/](../../custom_components/blaulichtsms/translations/) — mirror label
- [binary_sensor.py](../../custom_components/blaulichtsms/binary_sensor.py) — new sensor class + registration
- [test_blaulichtsms.py](../../custom_components/blaulichtsms/test_blaulichtsms.py) — new tests
