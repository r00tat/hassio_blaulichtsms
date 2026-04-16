"""BlaulichtSMS integration tests against the live Dashboard API.

Gated by ``SKIP_INTEGRATION_TEST``. Unit tests live in the sibling ``test_*.py``
modules.
"""

import asyncio
import json
import logging
import os
import unittest
from collections.abc import Coroutine
from typing import Any

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
