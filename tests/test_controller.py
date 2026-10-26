"""Unit tests for BlaulichtSmsController response handling."""

import unittest
from unittest.mock import AsyncMock, MagicMock

import aiohttp
from yarl import URL

from custom_components.blaulichtsms.blaulichtsms import BlaulichtSmsAuthenticationError, BlaulichtSmsController

_TOKEN = "secret-session-token"
_URL = URL(f"https://api.example.invalid/dashboard/{_TOKEN}")


def _request_info() -> aiohttp.RequestInfo:
    return aiohttp.RequestInfo(_URL, "GET", {}, _URL)


def _response(status: int) -> MagicMock:
    resp = MagicMock(spec=aiohttp.ClientResponse)
    resp.status = status
    resp.json = AsyncMock(return_value={"alarms": []})
    if status >= 400:
        resp.raise_for_status.side_effect = aiohttp.ClientResponseError(
            _request_info(), (), status=status, message="Server Error"
        )
    return resp


class TestHandleResponse(unittest.IsolatedAsyncioTestCase):
    """`_handle_response` must never leak the session token in its errors."""

    def setUp(self):
        """Create a controller."""
        self.controller = BlaulichtSmsController("1", "user", "pass")

    def assert_no_token(self, err: BaseException):
        """Assert the error, its cause and context do not carry the URL."""
        self.assertNotIn(_TOKEN, str(err))
        self.assertNotIn(_TOKEN, repr(err))
        self.assertIsNone(err.__cause__)
        self.assertTrue(err.__suppress_context__)

    async def test_ok_returns_json(self):
        """A 200 response returns the JSON body."""
        self.assertEqual(
            await self.controller._handle_response(_response(200)), {"alarms": []}
        )

    async def test_auth_failure(self):
        """401/403 still raise the authentication error."""
        with self.assertRaises(BlaulichtSmsAuthenticationError):
            await self.controller._handle_response(_response(401))

    async def test_server_error_hides_url(self):
        """A 5xx/429 error carries only the status code."""
        for status in (429, 500, 503):
            with self.subTest(status=status), self.assertRaises(
                aiohttp.ClientError
            ) as ctx:
                await self.controller._handle_response(_response(status))
            self.assertNotIsInstance(ctx.exception, aiohttp.ClientResponseError)
            self.assertIn(str(status), str(ctx.exception))
            self.assert_no_token(ctx.exception)

    async def test_invalid_json_hides_url(self):
        """A non-JSON body (ContentTypeError) does not leak the URL either."""
        resp = _response(200)
        resp.json.side_effect = aiohttp.ContentTypeError(
            _request_info(), (), status=200, message="unexpected mimetype"
        )
        with self.assertRaises(aiohttp.ClientError) as ctx:
            await self.controller._handle_response(resp)
        self.assertNotIsInstance(ctx.exception, aiohttp.ClientResponseError)
        self.assert_no_token(ctx.exception)
