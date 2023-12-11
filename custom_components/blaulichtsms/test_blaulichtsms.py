from typing import Any, Coroutine
import asyncio
import unittest
import os
import logging
import json

from .blaulichtsms import BlaulichtSmsController

log = logging.getLogger('TestBlaulichtSMS')


class TestBlaulichtsms(unittest.IsolatedAsyncioTestCase):
    """test blaulichtsms api"""

    async def asyncTearDown(self) -> Coroutine[Any, Any, None]:
        await asyncio.sleep(0)
        return await super().asyncTearDown()

    async def test_auth(self):
        log.info("tesing auth")
        blaulichtsms = BlaulichtSmsController(
            os.environ['BLAULICHTSMS_CUSTOMERID'],
            os.environ['BLAULICHTSMS_USERNAME'],
            os.environ['BLAULICHTSMS_PASSWORD'],
        )
        token = await blaulichtsms.get_session()
        log.info('token: %s', token)
        self.assertIsNotNone(token)

    async def test_alarms(self):
        """get alarms"""
        log.info("fetching alarms")
        blaulichtsms = BlaulichtSmsController(
            os.environ['BLAULICHTSMS_CUSTOMERID'],
            os.environ['BLAULICHTSMS_USERNAME'],
            os.environ['BLAULICHTSMS_PASSWORD'],
        )
        alarms = await blaulichtsms.get_anonymized_alarms()
        self.assertIsNotNone(alarms)

        log.info("alarms %s", json.dumps(alarms))
        self.assertGreater(len(alarms), 0)

    async def test_get_last_alarm(self):
        """get last alarm"""
        blaulichtsms = BlaulichtSmsController(
            os.environ['BLAULICHTSMS_CUSTOMERID'],
            os.environ['BLAULICHTSMS_USERNAME'],
            os.environ['BLAULICHTSMS_PASSWORD'],
        )
        log.info("fetch last alarm")
        alarm = await blaulichtsms.get_last_alarm()
        self.assertIsNotNone(alarm)
        log.info("alarm %s on %s", alarm.get('alarmText'), alarm.get("alarmDate"))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    unittest.main()
