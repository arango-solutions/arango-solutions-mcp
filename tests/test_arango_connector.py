"""Unit tests for ArangoDBConnector.connect() retry / backoff logic.

These tests are mock-based and do NOT require Docker or a live ArangoDB.
The patched seam is ``arango_connector.ArangoClient``; ``asyncio.sleep`` is
stubbed out so retries fast-forward.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arangodb_mcp import arango_connector
from arangodb_mcp.arango_connector import ArangoDBConnector, DatabaseAccessDenied, _is_auth_error
from arangodb_mcp.policy.actor_context import ArangoCredentials, RequestIdentity, identity_scope

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
        with (
            patch(
                "arangodb_mcp.arango_connector.ArangoClient", return_value=_ok_client()
            ) as mock_client_cls,
            patch("arangodb_mcp.arango_connector.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
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

        with (
            patch(
                "arangodb_mcp.arango_connector.ArangoClient", side_effect=clients
            ) as mock_client_cls,
            patch("arangodb_mcp.arango_connector.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            await connector.connect()

        assert mock_client_cls.call_count == 3
        assert mock_sleep.await_count == 2
        assert connector.server_version == "3.12.0"

    async def test_auth_failure_raises_immediately(self, connector, fast_settings):
        err = _FakeAuthError("HTTP 401: unauthorized")

        with (
            patch("arangodb_mcp.arango_connector.ArangoClient", side_effect=err) as mock_client_cls,
            patch("arangodb_mcp.arango_connector.asyncio.sleep", new=AsyncMock()) as mock_sleep,
            pytest.raises(_FakeAuthError),
        ):
            await connector.connect()

        assert mock_client_cls.call_count == 1
        mock_sleep.assert_not_awaited()

    async def test_http_401_raises_immediately(self, connector, fast_settings):
        err = _FakeAuthError("server said no")
        err.http_code = 401  # type: ignore[attr-defined]

        with (
            patch("arangodb_mcp.arango_connector.ArangoClient", side_effect=err) as mock_client_cls,
            patch("arangodb_mcp.arango_connector.asyncio.sleep", new=AsyncMock()) as mock_sleep,
            pytest.raises(_FakeAuthError),
        ):
            await connector.connect()

        assert mock_client_cls.call_count == 1
        mock_sleep.assert_not_awaited()

    async def test_value_error_short_circuits(self, connector, fast_settings, monkeypatch):
        # Force _connect_sync to raise ValueError by emptying the password.
        fake_pw = MagicMock()
        fake_pw.get_secret_value.return_value = ""
        monkeypatch.setattr(arango_connector.settings.arango, "root_password", fake_pw)

        with (
            patch(
                "arangodb_mcp.arango_connector.ArangoClient", return_value=_ok_client()
            ) as mock_client_cls,
            patch("arangodb_mcp.arango_connector.asyncio.sleep", new=AsyncMock()) as mock_sleep,
            pytest.raises(ValueError, match="ArangoDB password not configured"),
        ):
            await connector.connect()

        mock_client_cls.assert_not_called()
        mock_sleep.assert_not_awaited()

    async def test_exhausted_retries_raises_last(self, connector, fast_settings):
        # max_retries=3 → 4 total attempts, 3 sleeps between them.
        with (
            patch(
                "arangodb_mcp.arango_connector.ArangoClient",
                side_effect=ConnectionError("connection refused"),
            ) as mock_client_cls,
            patch("arangodb_mcp.arango_connector.asyncio.sleep", new=AsyncMock()) as mock_sleep,
            pytest.raises(ConnectionError, match="connection refused"),
        ):
            await connector.connect()

        assert mock_client_cls.call_count == 4  # max_retries + 1
        assert mock_sleep.await_count == 3  # max_retries

    async def test_backoff_doubling_capped_at_30s(self, connector, monkeypatch):
        monkeypatch.setattr(arango_connector.settings.server, "connect_max_retries", 5)
        monkeypatch.setattr(arango_connector.settings.server, "connect_initial_backoff", 20.0)

        sleep_calls: list[float] = []

        async def _record_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)

        with (
            patch(
                "arangodb_mcp.arango_connector.ArangoClient",
                side_effect=ConnectionError("connection refused"),
            ),
            patch("arangodb_mcp.arango_connector.asyncio.sleep", new=_record_sleep),
            pytest.raises(ConnectionError),
        ):
            await connector.connect()

        # 20 → min(40, 30)=30 → 30 → 30 → 30; 5 sleeps for max_retries=5.
        assert sleep_calls == [20.0, 30.0, 30.0, 30.0, 30.0]


def _request_identity(actor: str, database: str, username: str, password: str) -> RequestIdentity:
    credentials = ArangoCredentials(
        username=username,
        password=password,
        databases=frozenset({database}),
    )
    return RequestIdentity(
        actor_id=actor,
        issuer="https://issuer.example",
        subject=actor,
        oauth_scopes=frozenset({"mcp:read"}),
        databases=frozenset({database}),
        credentials=credentials,
    )


@pytest.mark.asyncio
async def test_concurrent_actors_use_isolated_server_side_credentials():
    connector = ArangoDBConnector()
    connector.client = MagicMock()

    async def connect_as(identity: RequestIdentity):
        with identity_scope(identity):
            await asyncio.sleep(0)
            connector.get_db(next(iter(identity.databases)))

    alice = _request_identity("alice", "tenant_a", "alice-db", "alice-secret")
    bob = _request_identity("bob", "tenant_b", "bob-db", "bob-secret")
    await asyncio.gather(connect_as(alice), connect_as(bob))

    calls = connector.client.db.call_args_list
    assert {
        (
            call.args[0],
            call.kwargs["username"],
            call.kwargs["password"],
        )
        for call in calls
    } == {
        ("tenant_a", "alice-db", "alice-secret"),
        ("tenant_b", "bob-db", "bob-secret"),
    }


def test_connector_denies_database_outside_request_allowlist():
    connector = ArangoDBConnector()
    connector.client = MagicMock()
    identity = _request_identity("alice", "tenant_a", "alice-db", "alice-secret")

    with identity_scope(identity), pytest.raises(DatabaseAccessDenied):
        connector.get_db("tenant_b")

    connector.client.db.assert_not_called()


def test_legacy_connector_path_preserves_configured_static_credentials():
    connector = ArangoDBConnector()
    connector.client = MagicMock()

    connector.get_db("legacy-db")

    connector.client.db.assert_called_once_with(
        "legacy-db",
        username=arango_connector.settings.arango.root_username,
        password=arango_connector.settings.arango.root_password.get_secret_value(),
    )
