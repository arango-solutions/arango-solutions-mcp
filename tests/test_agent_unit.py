"""Mock-based unit tests for ArangoDB MCP agents.

These tests validate agent logic WITHOUT a running ArangoDB instance.
All database interactions are mocked via unittest.mock, targeting
``arango_connector`` as imported by each module.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
from arango.exceptions import ArangoServerError

from agents.agent_base import SYSTEM_DB, ArangoAgentBase, handle_arango_errors  # noqa: F401

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_db(name: str = "testdb") -> MagicMock:
    """Return a lightweight MagicMock that quacks like a StandardDatabase."""
    db = MagicMock()
    db.name = name
    return db


def _arango_server_error(error_message: str = "server boom", error_code: int = 1234):
    """Build a realistic ArangoServerError."""
    resp = MagicMock()
    resp.status_code = 500
    resp.status_text = "Internal Server Error"
    resp.error_code = error_code
    resp.error_message = error_message
    resp.is_success = False
    request = MagicMock()
    request.method = "GET"
    request.url = "http://localhost:8529"
    return ArangoServerError(resp, request)


# ===================================================================
# 1. handle_arango_errors decorator tests
# ===================================================================


class TestHandleArangoErrors:
    """Tests for the ``@handle_arango_errors`` decorator."""

    @pytest.mark.asyncio
    async def test_catches_arango_server_error(self):
        class _Agent(ArangoAgentBase):
            @handle_arango_errors("TestAgent", "Test")
            async def arun(self, mcp_tool_inputs):
                raise _arango_server_error("db unavailable", 503)

        result = await _Agent().arun({})
        assert "error" in result
        assert result["error_code"] == 503
        assert "db unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_specific_exceptions_caught_before_arango_server_error(self):
        class _Agent(ArangoAgentBase):
            @handle_arango_errors("TestAgent", "Custom", specific_exceptions=(ValueError,))
            async def arun(self, mcp_tool_inputs):
                raise ValueError("bad value")

        result = await _Agent().arun({})
        assert "error" in result
        assert "bad value" in result["error"]
        assert result["error"].startswith("Custom Error:")

    @pytest.mark.asyncio
    async def test_generic_exception_returns_unexpected_error(self):
        class _Agent(ArangoAgentBase):
            @handle_arango_errors("TestAgent", "Test")
            async def arun(self, mcp_tool_inputs):
                raise RuntimeError("something broke")

        result = await _Agent().arun({})
        assert "unexpected error" in result["error"].lower()
        assert "something broke" in result["error"]

    @pytest.mark.asyncio
    async def test_success_returns_result_unchanged(self):
        class _Agent(ArangoAgentBase):
            @handle_arango_errors("TestAgent", "Test")
            async def arun(self, mcp_tool_inputs):
                return {"status": "ok", "count": 42}

        result = await _Agent().arun({})
        assert result == {"status": "ok", "count": 42}

    @pytest.mark.asyncio
    async def test_logger_called_on_error(self):
        class _Agent(ArangoAgentBase):
            @handle_arango_errors("TestAgent", "Test")
            async def arun(self, mcp_tool_inputs):
                raise _arango_server_error("logged error")

        with patch.object(logging.getLogger(__name__), "error") as mock_log:
            await _Agent().arun({})
            mock_log.assert_called_once()
            assert "logged error" in mock_log.call_args[0][0]

    @pytest.mark.asyncio
    async def test_error_label_appears_in_message(self):
        class _Agent(ArangoAgentBase):
            @handle_arango_errors("TestAgent", "My Custom Label")
            async def arun(self, mcp_tool_inputs):
                raise _arango_server_error("oops")

        result = await _Agent().arun({})
        assert result["error"].startswith("My Custom Label Error:")


# ===================================================================
# 2. ArangoAgentBase tests
# ===================================================================


class TestArangoAgentBase:
    """Tests for ``ArangoAgentBase`` helper methods."""

    @patch("agents.agent_base.arango_connector")
    def test_resolve_db_calls_get_db(self, mock_connector):
        mock_connector.get_db.return_value = _mock_db("mydb")

        class _Agent(ArangoAgentBase):
            async def arun(self, mcp_tool_inputs):
                pass

        agent = _Agent()
        db, name = agent.resolve_db("mydb")

        mock_connector.get_db.assert_called_once_with("mydb")
        assert name == "mydb"
        assert db.name == "mydb"

    @patch("agents.agent_base.arango_connector")
    def test_resolve_db_none_uses_db_name(self, mock_connector):
        mock_connector.get_db.return_value = _mock_db("default_db")

        class _Agent(ArangoAgentBase):
            async def arun(self, mcp_tool_inputs):
                pass

        agent = _Agent()
        db, name = agent.resolve_db(None)

        mock_connector.get_db.assert_called_once_with(None)
        assert name == "default_db"

    @pytest.mark.asyncio
    async def test_run_sync_wraps_sync_function(self):
        def _blocking(a, b):
            return a + b

        class _Agent(ArangoAgentBase):
            async def arun(self, mcp_tool_inputs):
                pass

        result = await _Agent.run_sync(_blocking, 3, 7)
        assert result == 10


# ===================================================================
# 3. Agent dispatch tests
# ===================================================================


class TestAQLExecutionAgent:
    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_empty_query_returns_error(self, mock_connector):
        from agents.aql_execution_agent import AQLExecutionAgent

        result = await AQLExecutionAgent().arun({"aql_query": "", "operation": "execute"})
        assert "error" in result
        assert "empty" in result["error"].lower()

    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_unknown_operation_falls_through_to_execute(self, mock_connector):
        """Non-recognised operations fall through to the default execute path,
        which still requires a non-empty query."""
        from agents.aql_execution_agent import AQLExecutionAgent

        result = await AQLExecutionAgent().arun(
            {"operation": "nonexistent", "aql_query": ""}
        )
        assert "error" in result


class TestDocumentCRUDAgent:
    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_unknown_operation_returns_error(self, mock_connector):
        from agents.document_crud_agent import DocumentCRUDAgent

        mock_connector.get_db.return_value = _mock_db()
        mock_connector.get_db.return_value.has_collection.return_value = True
        mock_connector.get_db.return_value.collection.return_value = MagicMock()

        result = await DocumentCRUDAgent().arun(
            {"operation": "fly_to_moon", "collection_name": "test"}
        )
        assert "error" in result
        assert "Unknown document operation" in result["error"]

    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_missing_collection_name_returns_error(self, mock_connector):
        from agents.document_crud_agent import DocumentCRUDAgent

        result = await DocumentCRUDAgent().arun(
            {"operation": "create_document", "document_data": {"x": 1}}
        )
        assert "error" in result
        assert "Collection name is required" in result["error"]


class TestCollectionManagementAgent:
    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_unknown_operation_returns_error(self, mock_connector):
        from agents.collection_management_agent import CollectionManagementAgent

        mock_connector.get_db.return_value = _mock_db()

        result = await CollectionManagementAgent().arun({"operation": "warp_drive"})
        assert "error" in result
        assert "Unknown collection operation" in result["error"]


class TestDatabaseManagementAgent:
    @pytest.mark.asyncio
    @patch("agents.database_management_agent.arango_connector")
    @patch("agents.agent_base.arango_connector")
    async def test_system_db_delete_guard(self, mock_base_conn, mock_db_conn):
        from agents.database_management_agent import DatabaseManagementAgent

        sys_db = _mock_db(SYSTEM_DB)
        sys_db.has_database.return_value = True
        mock_db_conn.get_system_db.return_value = sys_db

        result = await DatabaseManagementAgent().arun(
            {"operation": "delete_database", "database_name": SYSTEM_DB}
        )
        assert "error" in result
        assert "Cannot delete" in result["error"]
        assert SYSTEM_DB in result["error"]

    @pytest.mark.asyncio
    @patch("agents.database_management_agent.arango_connector")
    @patch("agents.agent_base.arango_connector")
    async def test_unknown_operation_returns_error(self, mock_base_conn, mock_db_conn):
        from agents.database_management_agent import DatabaseManagementAgent

        mock_db_conn.get_system_db.return_value = _mock_db()

        result = await DatabaseManagementAgent().arun({"operation": "teleport"})
        assert "error" in result
        assert "Unknown database operation" in result["error"]


class TestUserManagementAgent:
    @pytest.mark.asyncio
    @patch("agents.user_management_agent.arango_connector")
    @patch("agents.agent_base.arango_connector")
    async def test_invalid_permission_returns_error(self, mock_base_conn, mock_user_conn):
        from agents.user_management_agent import UserManagementAgent

        mock_user_conn.get_system_db.return_value = _mock_db()

        result = await UserManagementAgent().arun(
            {
                "operation": "grant_permission",
                "username": "alice",
                "permission": "superadmin",
                "database_name": "testdb",
            }
        )
        assert "error" in result
        assert "Invalid permission" in result["error"]
        assert "superadmin" in result["error"]

    @pytest.mark.asyncio
    @patch("agents.user_management_agent.arango_connector")
    @patch("agents.agent_base.arango_connector")
    async def test_unknown_operation_returns_error(self, mock_base_conn, mock_user_conn):
        from agents.user_management_agent import UserManagementAgent

        mock_user_conn.get_system_db.return_value = _mock_db()

        result = await UserManagementAgent().arun({"operation": "hack_the_planet"})
        assert "error" in result
        assert "Unknown user operation" in result["error"]


class TestTransactionManagementAgent:
    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_js_transaction_disabled_by_default(self, mock_connector):
        from agents.transaction_management_agent import TransactionManagementAgent

        mock_connector.get_db.return_value = _mock_db()

        with patch("agents.transaction_management_agent.settings") as mock_settings:
            mock_settings.server.enable_js_transactions = False
            result = await TransactionManagementAgent().arun(
                {"operation": "execute_transaction", "command": "function(){}"}
            )

        assert "error" in result
        assert "disabled" in result["error"].lower()

    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_unknown_operation_returns_error(self, mock_connector):
        from agents.transaction_management_agent import TransactionManagementAgent

        mock_connector.get_db.return_value = _mock_db()

        result = await TransactionManagementAgent().arun({"operation": "rewind_time"})
        assert "error" in result
        assert "Unknown transaction operation" in result["error"]


class TestManualManagementAgent:
    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_unknown_manual_name_returns_error(self, mock_connector):
        from agents.manual_management_agent import ManualManagementAgent

        result = await ManualManagementAgent().arun(
            {"operation": "get_aql_manual", "manual_name": "nonexistent_manual_xyz"}
        )
        assert "error" in result
        assert "Unknown manual" in result["error"]

    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_unknown_operation_returns_error(self, mock_connector):
        from agents.manual_management_agent import ManualManagementAgent

        result = await ManualManagementAgent().arun(
            {"operation": "delete_all_manuals", "manual_name": "aql"}
        )
        assert "error" in result
        assert "Unknown manual operation" in result["error"]


class TestGraphTraversalAgent:
    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_missing_start_vertex_returns_error(self, mock_connector):
        from agents.graph_traversal_agent import GraphTraversalAgent

        mock_connector.get_db.return_value = _mock_db()

        result = await GraphTraversalAgent().arun(
            {
                "operation": "traverse",
                "graph_name": "social",
                "direction": "OUTBOUND",
            }
        )
        assert "error" in result
        assert "start_vertex" in result["error"].lower()

    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_invalid_direction_returns_error(self, mock_connector):
        from agents.graph_traversal_agent import GraphTraversalAgent

        mock_connector.get_db.return_value = _mock_db()

        result = await GraphTraversalAgent().arun(
            {
                "operation": "traverse",
                "start_vertex": "users/1",
                "direction": "SIDEWAYS",
                "graph_name": "social",
            }
        )
        assert "error" in result
        assert "Invalid direction" in result["error"]
        assert "SIDEWAYS" in result["error"]


class TestVectorSearchAgent:
    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_invalid_metric_returns_error(self, mock_connector):
        from agents.vector_search_agent import VectorSearchAgent

        mock_connector.get_db.return_value = _mock_db()

        result = await VectorSearchAgent().arun(
            {
                "operation": "vector_search",
                "collection_name": "docs",
                "vector_field": "embedding",
                "query_vector": [0.1, 0.2],
                "metric": "manhattan",
            }
        )
        assert "error" in result
        assert "Unsupported metric" in result["error"]
        assert "manhattan" in result["error"]

    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_missing_collection_returns_error(self, mock_connector):
        from agents.vector_search_agent import VectorSearchAgent

        mock_connector.get_db.return_value = _mock_db()

        result = await VectorSearchAgent().arun(
            {
                "operation": "vector_search",
                "collection_name": "",
                "vector_field": "embedding",
                "query_vector": [0.1],
            }
        )
        assert "error" in result
        assert "collection_name" in result["error"].lower()

    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_unknown_operation_returns_error(self, mock_connector):
        from agents.vector_search_agent import VectorSearchAgent

        mock_connector.get_db.return_value = _mock_db()

        result = await VectorSearchAgent().arun({"operation": "quantum_search"})
        assert "error" in result
        assert "Unknown vector operation" in result["error"]


# ===================================================================
# 4. Input validation tests (validate_aql_identifier)
# ===================================================================


class TestInputValidation:
    """Tests that agents using ``validate_aql_identifier`` reject unsafe names."""

    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_graph_traversal_rejects_injection_in_graph_name(self, mock_connector):
        """A graph_name containing backtick injection should be rejected by
        ``validate_aql_identifier`` and surface as an error via the decorator."""
        from agents.graph_traversal_agent import GraphTraversalAgent

        mock_connector.get_db.return_value = _mock_db()

        result = await GraphTraversalAgent().arun(
            {
                "operation": "traverse",
                "start_vertex": "users/1",
                "direction": "OUTBOUND",
                "graph_name": "evil`; DROP DATABASE _system; //",
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_vector_search_rejects_bad_collection_name(self, mock_connector):
        from agents.vector_search_agent import VectorSearchAgent

        mock_connector.get_db.return_value = _mock_db()
        db = mock_connector.get_db.return_value
        cursor = MagicMock()
        cursor.__iter__ = MagicMock(return_value=iter([]))
        cursor.count.return_value = 0
        db.aql.execute.return_value = cursor

        result = await VectorSearchAgent().arun(
            {
                "operation": "vector_search",
                "collection_name": "col'; DROP TABLE--",
                "vector_field": "vec",
                "query_vector": [1.0],
                "metric": "cosine",
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_vector_search_rejects_bad_vector_field(self, mock_connector):
        from agents.vector_search_agent import VectorSearchAgent

        mock_connector.get_db.return_value = _mock_db()

        result = await VectorSearchAgent().arun(
            {
                "operation": "vector_search",
                "collection_name": "docs",
                "vector_field": "emb`; RETURN 1",
                "query_vector": [1.0],
                "metric": "cosine",
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_graph_traversal_rejects_special_char_edge_collection(self, mock_connector):
        from agents.graph_traversal_agent import GraphTraversalAgent

        mock_connector.get_db.return_value = _mock_db()

        result = await GraphTraversalAgent().arun(
            {
                "operation": "traverse",
                "start_vertex": "users/1",
                "direction": "OUTBOUND",
                "edge_collections": ["valid_edges", "bad collection!"],
            }
        )
        assert "error" in result

    @pytest.mark.asyncio
    @patch("agents.agent_base.arango_connector")
    async def test_collection_name_with_spaces_rejected(self, mock_connector):
        from agents.vector_search_agent import VectorSearchAgent

        mock_connector.get_db.return_value = _mock_db()

        result = await VectorSearchAgent().arun(
            {
                "operation": "vector_search",
                "collection_name": "my collection",
                "vector_field": "vec",
                "query_vector": [0.5],
                "metric": "cosine",
            }
        )
        assert "error" in result
