"""Unit tests for ArangoDBConnector.connect() retry / backoff logic.

These tests are mock-based and do NOT require Docker or a live ArangoDB.
The patched seam is ``arango_connector.ArangoClient``; ``asyncio.sleep`` is
stubbed out so retries fast-forward.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import arango_connector
from arango_connector import ArangoDBConnector, _is_auth_error

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeAuthError(Exception):
    """Stand-in for an authentication/authorization failure from the driver."""


def _ok_client() -> MagicMock:
    """Return a MagicMock ArangoClient whose ``.db().version()`` succeeds."""
    client = MagicMock()
    db = MagicMock()
    db.version.return_value = "3.12.0"
    client.db.return_value = db
    return client


@pytest.fixture
def connector() -> ArangoDBConnector:
    return ArangoDBConnector()


@pytest.fixture
def fast_settings(monkeypatch):
    """Default to a small retry budget with fast backoff for most tests."""
    monkeypatch.setattr(arango_connector.settings.server, "connect_max_retries", 3)
    monkeypatch.setattr(arango_connector.settings.server, "connect_initial_backoff", 0.01)


# ---------------------------------------------------------------------------
# _is_auth_error helper
# ---------------------------------------------------------------------------


class TestIsAuthError:
    def test_message_unauthorized(self):
        assert _is_auth_error(Exception("HTTP 401: unauthorized"))

    def test_message_authentication(self):
        assert _is_auth_error(Exception("authentication failed"))

    def test_message_forbidden(self):
        assert _is_auth_error(Exception("forbidden"))

    def test_http_code_401(self):
        err = _FakeAuthError("nope")
        err.http_code = 401  # type: ignore[attr-defined]
        assert _is_auth_error(err)

    def test_http_code_403(self):
        err = _FakeAuthError("nope")
        err.http_code = 403  # type: ignore[attr-defined]
        assert _is_auth_error(err)

    def test_transient_not_auth(self):
        assert not _is_auth_error(ConnectionError("connection refused"))


# ---------------------------------------------------------------------------
# connect() behaviour
# ---------------------------------------------------------------------------


class TestConnectRetry:
    async def test_success_on_first_attempt(self, connector, fast_settings):
        with patch(
            "arango_connector.ArangoClient", return_value=_ok_client()
        ) as mock_client_cls, patch(
            "arango_connector.asyncio.sleep", new=AsyncMock()
        ) as mock_sleep:
            await connector.connect()

        mock_client_cls.assert_called_once()
        mock_sleep.assert_not_awaited()
        assert connector.server_version == "3.12.0"

    async def test_two_transient_failures_then_success(self, connector, fast_settings):
        clients = [
            ConnectionError("connection refused"),
            ConnectionError("connection refused"),
            _ok_client(),
        ]

        with patch(
            "arango_connector.ArangoClient", side_effect=clients
        ) as mock_client_cls, patch(
            "arango_connector.asyncio.sleep", new=AsyncMock()
        ) as mock_sleep:
            await connector.connect()

        assert mock_client_cls.call_count == 3
        assert mock_sleep.await_count == 2
        assert connector.server_version == "3.12.0"

    async def test_auth_failure_raises_immediately(self, connector, fast_settings):
        err = _FakeAuthError("HTTP 401: unauthorized")

        with patch(
            "arango_connector.ArangoClient", side_effect=err
        ) as mock_client_cls, patch(
            "arango_connector.asyncio.sleep", new=AsyncMock()
        ) as mock_sleep, pytest.raises(_FakeAuthError):
            await connector.connect()

        assert mock_client_cls.call_count == 1
        mock_sleep.assert_not_awaited()

    async def test_http_401_raises_immediately(self, connector, fast_settings):
        err = _FakeAuthError("server said no")
        err.http_code = 401  # type: ignore[attr-defined]

        with patch(
            "arango_connector.ArangoClient", side_effect=err
        ) as mock_client_cls, patch(
            "arango_connector.asyncio.sleep", new=AsyncMock()
        ) as mock_sleep, pytest.raises(_FakeAuthError):
            await connector.connect()

        assert mock_client_cls.call_count == 1
        mock_sleep.assert_not_awaited()

    async def test_value_error_short_circuits(self, connector, fast_settings, monkeypatch):
        # Force _connect_sync to raise ValueError by emptying the password.
        fake_pw = MagicMock()
        fake_pw.get_secret_value.return_value = ""
        monkeypatch.setattr(arango_connector.settings.arango, "root_password", fake_pw)

        with patch(
            "arango_connector.ArangoClient", return_value=_ok_client()
        ) as mock_client_cls, patch(
            "arango_connector.asyncio.sleep", new=AsyncMock()
        ) as mock_sleep, pytest.raises(ValueError, match="ArangoDB password not configured"):
            await connector.connect()

        mock_client_cls.assert_not_called()
        mock_sleep.assert_not_awaited()

    async def test_exhausted_retries_raises_last(self, connector, fast_settings):
        # max_retries=3 → 4 total attempts, 3 sleeps between them.
        with patch(
            "arango_connector.ArangoClient",
            side_effect=ConnectionError("connection refused"),
        ) as mock_client_cls, patch(
            "arango_connector.asyncio.sleep", new=AsyncMock()
        ) as mock_sleep, pytest.raises(ConnectionError, match="connection refused"):
            await connector.connect()

        assert mock_client_cls.call_count == 4  # max_retries + 1
        assert mock_sleep.await_count == 3  # max_retries

    async def test_backoff_doubling_capped_at_30s(self, connector, monkeypatch):
        monkeypatch.setattr(arango_connector.settings.server, "connect_max_retries", 5)
        monkeypatch.setattr(arango_connector.settings.server, "connect_initial_backoff", 20.0)

        sleep_calls: list[float] = []

        async def _record_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with patch(
            "arango_connector.ArangoClient",
            side_effect=ConnectionError("connection refused"),
        ), patch(
            "arango_connector.asyncio.sleep", new=_record_sleep
        ), pytest.raises(ConnectionError):
            await connector.connect()

        # 20 → min(40, 30)=30 → 30 → 30 → 30; 5 sleeps for max_retries=5.
        assert sleep_calls == [20.0, 30.0, 30.0, 30.0, 30.0]
