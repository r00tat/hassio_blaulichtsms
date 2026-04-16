# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Home Assistant custom integration (`custom_components/blaulichtsms/`) that polls the BlaulichtSMS Dashboard API for alarms/infos and exposes them as Home Assistant entities. Distributed via HACS.

## Environment & Common Commands

The venv is managed with [`uv`](https://docs.astral.sh/uv/). Bootstrap is done by `./dev.sh` (creates `.venv`, installs `requirements.txt`, rsyncs the component into `config/custom_components/blaulichtsms/`, then runs Home Assistant in Docker on port 8123).

Run python entry points via `uv run` — do not activate the venv manually. Examples:

```bash
uv run python -m ruff check                         # lint
uv run python -m unittest discover -v               # run all tests (from repo root)
uv run python -m unittest discover -s custom_components/blaulichtsms -t . -v  # same, with explicit start dir — -t must point at the repo root so the package resolves
uv run python -m unittest custom_components.blaulichtsms.test_binary_sensor.TestNewAlarmActiveSensor -v
uv run python -m unittest custom_components.blaulichtsms.test_binary_sensor.TestNewAlarmActiveSensor.test_new_alarm_forces_false_then_true
```

Tests are split by module:

- `test_blaulichtsms.py` — `TestBlaulichtsms` integration tests that hit the live API; skipped when `SKIP_INTEGRATION_TEST=true` (CI sets this).
- `test_binary_sensor.py` — unit tests for the binary sensors (`TestNewAlarmActiveSensor`, `TestAlarmActiveSensor`, `TestNeedsAcknowledgementSensor`).
- `test_coordinator.py` — `TestCoordinatorIsAlarmActive` for `BlaulichtSMSCoordinator._is_alarm_active`.
- `test_sensor.py` — `TestSensorEntity` and `TestAlarmHelpers` for the generic entity and pure helpers.
- `_test_fixtures.py` — shared `make_alarm` / `wrap` helpers (not a test module; does not match unittest discovery).

All non-integration tests have no network dependency and always run.

`./dev.sh` restarts the `homeassistant` Docker container after syncing the component; use it to exercise changes against a real Home Assistant.

## Architecture

Single-integration layout under `custom_components/blaulichtsms/`:

- [blaulichtsms.py](custom_components/blaulichtsms/blaulichtsms.py) — `BlaulichtSmsController`, the async aiohttp client for the Dashboard API (login → session token → `get_alarms` / `get_last_alarm`). Has no Home Assistant dependencies; integration tests exercise it directly with credentials from env vars.
- [coordinator.py](custom_components/blaulichtsms/coordinator.py) — `BlaulichtSMSCoordinator` wraps the controller in a `DataUpdateCoordinator` with a 30s poll. A class-level `coordinators` dict keyed by customer id keeps a single coordinator per config entry; `get_coordinator()` is the factory. `_async_update_data` calls `get_last_alarm()`, so `coordinator.data` is the latest alarm dict (or `None`).
- [config_flow.py](custom_components/blaulichtsms/config_flow.py) — UI-based setup and options flow; validates credentials by calling `get_last_alarm()` once before creating the entry.
- [sensor.py](custom_components/blaulichtsms/sensor.py) — One `BlaulichtSMSEntity` per field in `SENSOR_FIELDS` (a generic entity that dispatches on `attribute` name). Fields ending in `date` are marked `SensorDeviceClass.TIMESTAMP`. Special handling exists for `alarmText`, `alarmGroups`, `recipients`, and `CONF_TRACK_RECIPIENT`. An extra `CONF_TRACK_RECIPIENT` entity is added only when that option is configured.
- [binary_sensor.py](custom_components/blaulichtsms/binary_sensor.py) — Two binary sensors:
  - `BlaulichtSMSAlarmActiveSensor`: true while `now < alarmDate + CONF_ALARM_DURATION`.
  - `BlaulichtSMSNewAlarmActiveSensor`: edge-triggered. On a new `alarmId` it forces `False` then evaluates the target (window + optional recipient-confirmation gate), writing state twice so automations see a genuine `off → on` transition.
- [schema.py](custom_components/blaulichtsms/schema.py) / [constants.py](custom_components/blaulichtsms/constants.py) — voluptuous schemas for user + options flow and the `DOMAIN` / `CONF_*` / `DEFAULT_*` constants.
- [__init__.py](custom_components/blaulichtsms/__init__.py) — `async_setup_entry` forwards to `sensor` and `binary_sensor` platforms.

Data flow: config entry → `BlaulichtSMSCoordinator.get_coordinator` (singleton per customer id) → `BlaulichtSmsController.get_last_alarm()` every 30s → entities receive `_handle_coordinator_update` and derive their state from `coordinator.data`.

## Conventions

- Ruff config is in [.ruff.toml](.ruff.toml) (target `py310`, line length 88, Home Assistant rule set). Run ruff and fix warnings before committing.
- Version lives in two places: [manifest.json](custom_components/blaulichtsms/manifest.json) `version` and [constants.py](custom_components/blaulichtsms/constants.py) `VERSION`. Keep both in sync when bumping.
- User-facing strings are in [strings.json](custom_components/blaulichtsms/strings.json) plus German/English translations in [translations/](custom_components/blaulichtsms/translations/). New `CONF_*` options require entries in all three.
- The integration is loaded as a package (`custom_components.blaulichtsms.…`) so tests and imports use the full dotted path. Avoid relative scripts outside that package.
