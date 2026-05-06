"""Tests for handle_arango_errors decorator and ArangoAgentBase base class."""

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class FakeArangoServerError(Exception):
    """Mimics arango.exceptions.ArangoServerError for testing without importing it."""

    def __init__(self, error_message: str = "server error", error_code: int = 1234):
        self.error_message = error_message
        self.error_code = error_code
        super().__init__(error_message)


class CustomDomainError(Exception):
    """A specific exception to test `specific_exceptions` handling."""

    def __init__(self, msg: str = "domain boom", error_code: int = 9999):
        self.error_message = msg
        self.error_code = error_code
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Patch ArangoServerError at the module level so the decorator picks it up
# without importing the real arango driver at test-collection time.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _patch_arango_server_error():
    with patch("agents.agent_base.ArangoServerError", FakeArangoServerError):
        yield


# ---------------------------------------------------------------------------
# Import helpers – must happen *after* the autouse fixture is defined so the
# module is importable even when the real arango package is absent.  We
# re-import inside each fixture/test that needs them so the patch is active.
# ---------------------------------------------------------------------------


def _import_agent_base():
    from agents.agent_base import SYSTEM_DB, ArangoAgentBase, handle_arango_errors

    return ArangoAgentBase, handle_arango_errors, SYSTEM_DB


# ============================= SYSTEM_DB ===================================


class TestSystemDB:
    def test_system_db_equals_underscore_system(self):
        _, _, SYSTEM_DB = _import_agent_base()
        assert SYSTEM_DB == "_system"


# ======================== handle_arango_errors =============================


def _make_agent_class():
    """Build a minimal concrete agent class decorated with handle_arango_errors."""
    ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

    class StubAgent(ArangoAgentBase):
        @handle_arango_errors("StubAgent", error_label="Stub")
        async def arun(self, mcp_tool_inputs: dict[str, Any]) -> dict[str, Any]:
            """Docstring for arun."""
            return mcp_tool_inputs

    return StubAgent


def _make_agent_class_with_specific(specific_exc: tuple[type[Exception], ...]):
    ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

    class StubAgent(ArangoAgentBase):
        @handle_arango_errors(
            "StubAgent",
            error_label="Domain",
            specific_exceptions=specific_exc,
        )
        async def arun(self, mcp_tool_inputs: dict[str, Any]) -> dict[str, Any]:
            raise mcp_tool_inputs["raise"]

    return StubAgent


class TestHandleArangoErrorsDecorator:
    """Tests for the handle_arango_errors decorator."""

    @pytest.mark.asyncio
    async def test_success_passes_through(self):
        agent = _make_agent_class()()
        result = await agent.arun({"key": "value"})
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_arango_server_error_returns_error_dict(self):
        ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

        class FailAgent(ArangoAgentBase):
            @handle_arango_errors("FailAgent")
            async def arun(self, mcp_tool_inputs, **kw):
                raise FakeArangoServerError("bad query", 1203)

        result = await FailAgent().arun({})
        assert "error" in result
        assert "error_code" in result

    @pytest.mark.asyncio
    async def test_error_value_contains_error_label_prefix(self):
        ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

        class FailAgent(ArangoAgentBase):
            @handle_arango_errors("FailAgent", error_label="AQL")
            async def arun(self, mcp_tool_inputs, **kw):
                raise FakeArangoServerError("syntax error")

        result = await FailAgent().arun({})
        assert result["error"].startswith("AQL Error:")

    @pytest.mark.asyncio
    async def test_error_code_from_exception_attribute(self):
        ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

        class FailAgent(ArangoAgentBase):
            @handle_arango_errors("FailAgent")
            async def arun(self, mcp_tool_inputs, **kw):
                raise FakeArangoServerError("oops", 4242)

        result = await FailAgent().arun({})
        assert result["error_code"] == 4242

    @pytest.mark.asyncio
    async def test_specific_exceptions_caught_before_arango_server_error(self):
        """specific_exceptions should be caught by the same handler as ArangoServerError."""
        Agent = _make_agent_class_with_specific((CustomDomainError,))
        result = await Agent().arun({"raise": CustomDomainError("custom fail", 9001)})
        assert "error" in result
        assert result["error"].startswith("Domain Error:")
        assert result["error_code"] == 9001

    @pytest.mark.asyncio
    async def test_generic_exception_returns_unexpected_message(self):
        ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

        class FailAgent(ArangoAgentBase):
            @handle_arango_errors("FailAgent")
            async def arun(self, mcp_tool_inputs, **kw):
                raise RuntimeError("kaboom")

        result = await FailAgent().arun({})
        assert "An unexpected error occurred" in result["error"]
        assert "kaboom" in result["error"]

    @pytest.mark.asyncio
    async def test_logger_error_on_arango_server_error(self):
        ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

        class FailAgent(ArangoAgentBase):
            @handle_arango_errors("FailAgent")
            async def arun(self, mcp_tool_inputs, **kw):
                raise FakeArangoServerError("log me")

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await FailAgent().arun({})
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "FailAgent" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_logger_error_with_exc_info_on_generic_exception(self):
        ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

        class FailAgent(ArangoAgentBase):
            @handle_arango_errors("FailAgent")
            async def arun(self, mcp_tool_inputs, **kw):
                raise ValueError("unexpected")

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            await FailAgent().arun({})
            mock_logger.error.assert_called_once()
            call_kwargs = mock_logger.error.call_args[1]
            assert call_kwargs.get("exc_info") is True

    def test_decorated_function_preserves_name_and_docstring(self):
        Agent = _make_agent_class()
        assert Agent.arun.__name__ == "arun"
        assert "Docstring for arun" in (Agent.arun.__doc__ or "")

    @pytest.mark.asyncio
    async def test_decorator_works_on_async_method(self):
        """Verify the wrapper itself is a coroutine function."""
        Agent = _make_agent_class()
        assert asyncio.iscoroutinefunction(Agent.arun)
        result = await Agent().arun({"async": True})
        assert result == {"async": True}


# ========================= ArangoAgentBase =================================


class TestArangoAgentBase:
    """Tests for the ArangoAgentBase base class."""

    def test_cannot_instantiate_without_arun(self):
        ArangoAgentBase, _, _ = _import_agent_base()

        with pytest.raises(TypeError):
            ArangoAgentBase()

    def test_resolve_db_with_explicit_name(self):
        ArangoAgentBase, _, _ = _import_agent_base()
        Agent = _make_agent_class()
        agent = Agent()

        mock_db = MagicMock()
        mock_db.name = "fallback"

        with patch("agents.agent_base.arango_connector") as mock_conn:
            mock_conn.get_db.return_value = mock_db
            db, name = agent.resolve_db("my_database")

        assert db is mock_db
        assert name == "my_database"

    def test_resolve_db_none_falls_back_to_db_name(self):
        Agent = _make_agent_class()
        agent = Agent()

        mock_db = MagicMock()
        mock_db.name = "fallback_db"

        with patch("agents.agent_base.arango_connector") as mock_conn:
            mock_conn.get_db.return_value = mock_db
            db, name = agent.resolve_db(None)

        assert db is mock_db
        assert name == "fallback_db"

    def test_resolve_db_calls_get_db_with_name(self):
        Agent = _make_agent_class()
        agent = Agent()

        mock_db = MagicMock()
        with patch("agents.agent_base.arango_connector") as mock_conn:
            mock_conn.get_db.return_value = mock_db
            agent.resolve_db("target_db")
            mock_conn.get_db.assert_called_once_with("target_db")

    @pytest.mark.asyncio
    async def test_run_sync_executes_sync_function(self):
        Agent = _make_agent_class()

        def add(a, b):
            return a + b

        result = await Agent.run_sync(add, 3, 4)
        assert result == 7


# ===================== on_arango_error callback ============================


class TestOnArangoErrorCallback:
    """Tests for the on_arango_error callback parameter on handle_arango_errors."""

    @pytest.mark.asyncio
    async def test_callback_dict_short_circuits_arango_server_error(self):
        ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

        override = {"status": "handled", "detail": "swapped"}

        class FailAgent(ArangoAgentBase):
            @handle_arango_errors(
                "FailAgent",
                error_label="Stub",
                on_arango_error=lambda exc: override,
            )
            async def arun(self, mcp_tool_inputs, **kw):
                raise FakeArangoServerError("boom", 1111)

        result = await FailAgent().arun({})
        assert result is override
        assert "error" not in result
        assert "error_code" not in result

    @pytest.mark.asyncio
    async def test_callback_none_falls_through_for_arango_server_error(self):
        ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

        class FailAgent(ArangoAgentBase):
            @handle_arango_errors(
                "FailAgent",
                error_label="Stub",
                on_arango_error=lambda exc: None,
            )
            async def arun(self, mcp_tool_inputs, **kw):
                raise FakeArangoServerError("fallthrough", 2222)

        result = await FailAgent().arun({})
        assert result["error"].startswith("Stub Error:")
        assert "fallthrough" in result["error"]
        assert result["error_code"] == 2222

    @pytest.mark.asyncio
    async def test_callback_fires_for_specific_exception(self):
        ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

        captured: list[Exception] = []

        def cb(exc: Exception):
            captured.append(exc)
            return {"handled_specific": True, "msg": str(exc)}

        class FailAgent(ArangoAgentBase):
            @handle_arango_errors(
                "FailAgent",
                error_label="Stub",
                specific_exceptions=(ValueError,),
                on_arango_error=cb,
            )
            async def arun(self, mcp_tool_inputs, **kw):
                raise ValueError("bad arg")

        result = await FailAgent().arun({})
        assert result == {"handled_specific": True, "msg": "bad arg"}
        assert len(captured) == 1
        assert isinstance(captured[0], ValueError)

    @pytest.mark.asyncio
    async def test_callback_fires_for_generic_exception_and_returns_dict(self):
        ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

        captured: list[Exception] = []

        def cb(exc: Exception):
            captured.append(exc)
            return {"handled_generic": True}

        class FailAgent(ArangoAgentBase):
            @handle_arango_errors(
                "FailAgent",
                error_label="Stub",
                on_arango_error=cb,
            )
            async def arun(self, mcp_tool_inputs, **kw):
                raise RuntimeError("totally unexpected")

        result = await FailAgent().arun({})
        assert result == {"handled_generic": True}
        assert len(captured) == 1
        assert isinstance(captured[0], RuntimeError)

    @pytest.mark.asyncio
    async def test_callback_not_invoked_on_success(self):
        ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

        calls: list[Exception] = []

        def cb(exc: Exception):
            calls.append(exc)
            return {"should_not_appear": True}

        class OkAgent(ArangoAgentBase):
            @handle_arango_errors(
                "OkAgent",
                error_label="Stub",
                on_arango_error=cb,
            )
            async def arun(self, mcp_tool_inputs, **kw):
                return {"ok": mcp_tool_inputs.get("value")}

        result = await OkAgent().arun({"value": 42})
        assert result == {"ok": 42}
        assert calls == []

    @pytest.mark.asyncio
    async def test_backward_compat_no_callback_uses_standard_error_dict(self):
        ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

        class FailAgent(ArangoAgentBase):
            @handle_arango_errors("FailAgent", error_label="Stub")
            async def arun(self, mcp_tool_inputs, **kw):
                raise FakeArangoServerError("legacy", 3333)

        result = await FailAgent().arun({})
        assert result == {
            "error": "Stub Error: legacy",
            "error_code": 3333,
        }

    @pytest.mark.asyncio
    async def test_logging_still_happens_before_callback(self):
        ArangoAgentBase, handle_arango_errors, _ = _import_agent_base()

        class FailAgent(ArangoAgentBase):
            @handle_arango_errors(
                "FailAgent",
                error_label="Stub",
                on_arango_error=lambda exc: {"swapped": True},
            )
            async def arun(self, mcp_tool_inputs, **kw):
                raise FakeArangoServerError("audit me")

        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            result = await FailAgent().arun({})
            mock_logger.error.assert_called_once()
            assert result == {"swapped": True}


# ============================ pack_optional ================================


class TestPackOptional:
    """Tests for ArangoAgentBase.pack_optional helper."""

    def test_skips_none_values(self):
        ArangoAgentBase, _, _ = _import_agent_base()
        result = ArangoAgentBase.pack_optional({}, a=1, b=None, c="x")
        assert result == {"a": 1, "c": "x"}

    def test_preserves_existing_keys_and_adds_new(self):
        ArangoAgentBase, _, _ = _import_agent_base()
        result = ArangoAgentBase.pack_optional({"existing": True}, new_key=42)
        assert result == {"existing": True, "new_key": 42}

    def test_all_none_kwargs_leaves_payload_unchanged(self):
        ArangoAgentBase, _, _ = _import_agent_base()
        payload = {"keep": "me"}
        result = ArangoAgentBase.pack_optional(payload, a=None, b=None)
        assert result == {"keep": "me"}

    def test_returns_same_dict_object_mutates_in_place(self):
        ArangoAgentBase, _, _ = _import_agent_base()
        payload: dict[str, Any] = {"start": 1}
        result = ArangoAgentBase.pack_optional(payload, added="yes", skipped=None)
        assert result is payload
        assert payload == {"start": 1, "added": "yes"}
