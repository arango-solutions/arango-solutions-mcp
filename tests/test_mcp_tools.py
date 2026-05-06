"""Tests for MCP tool wrappers in mcp_tools/.

Verifies that each tool function constructs the correct operation dict and
delegates to the corresponding agent's ``arun`` method.
"""

import os

os.environ.setdefault("ARANGO_HOSTS", "http://localhost:8529")
os.environ.setdefault("ARANGO_ROOT_USERNAME", "root")
os.environ.setdefault("ARANGO_ROOT_PASSWORD", "test_password")

from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# database_tools
# ---------------------------------------------------------------------------


class TestDatabaseTools:
    @pytest.mark.asyncio
    @patch("mcp_tools.database_tools.db_agent")
    async def test_list_databases(self, mock_agent):
        from mcp_tools.database_tools import list_databases

        mock_agent.arun = AsyncMock(return_value={"databases": []})
        result = await list_databases()

        mock_agent.arun.assert_called_once_with({"operation": "list_databases"})
        assert result == {"databases": []}

    @pytest.mark.asyncio
    @patch("mcp_tools.database_tools.db_agent")
    async def test_create_database(self, mock_agent):
        from mcp_tools.database_tools import create_database

        mock_agent.arun = AsyncMock(return_value={"success": True})
        result = await create_database(database_name="test_db")

        mock_agent.arun.assert_called_once_with(
            {"operation": "create_database", "database_name": "test_db"}
        )
        assert result == {"success": True}

    @pytest.mark.asyncio
    @patch("mcp_tools.database_tools.db_agent")
    async def test_delete_database_system_guard(self, mock_agent):
        from mcp_tools.database_tools import delete_database

        mock_agent.arun = AsyncMock()
        result = await delete_database(database_name="_system")

        mock_agent.arun.assert_not_called()
        assert "error" in result
        assert "_system" in result["error"]

    @pytest.mark.asyncio
    @patch("mcp_tools.database_tools.db_agent")
    async def test_delete_database_valid(self, mock_agent):
        from mcp_tools.database_tools import delete_database

        mock_agent.arun = AsyncMock(return_value={"success": True})
        result = await delete_database(database_name="old_db")

        mock_agent.arun.assert_called_once_with(
            {"operation": "delete_database", "database_name": "old_db"}
        )
        assert result == {"success": True}


# ---------------------------------------------------------------------------
# aql_tools
# ---------------------------------------------------------------------------


class TestAqlTools:
    @pytest.mark.asyncio
    @patch("mcp_tools.aql_tools.aql_agent")
    async def test_execute_aql_query(self, mock_agent):
        from mcp_tools.aql_tools import execute_aql

        mock_agent.arun = AsyncMock(return_value={"results": [1, 2, 3]})
        result = await execute_aql(
            aql_query="FOR d IN col RETURN d",
            bind_vars={"@col": "users"},
            database_name="mydb",
            max_runtime=None,
        )

        mock_agent.arun.assert_called_once_with(
            {
                "operation": "execute",
                "aql_query": "FOR d IN col RETURN d",
                "bind_vars": {"@col": "users"},
                "database_name": "mydb",
                "max_runtime": None,
            }
        )
        assert result == {"results": [1, 2, 3]}

    @pytest.mark.asyncio
    @patch("mcp_tools.aql_tools.aql_agent")
    async def test_execute_aql_query_defaults_bind_vars(self, mock_agent):
        from mcp_tools.aql_tools import execute_aql

        mock_agent.arun = AsyncMock(return_value={"results": []})
        await execute_aql(aql_query="RETURN 1", bind_vars=None, database_name=None)

        call_args = mock_agent.arun.call_args[0][0]
        assert call_args["bind_vars"] == {}

    @pytest.mark.asyncio
    @patch("mcp_tools.aql_tools.aql_agent")
    async def test_execute_aql_query_passes_max_runtime(self, mock_agent):
        from mcp_tools.aql_tools import execute_aql

        mock_agent.arun = AsyncMock(return_value={"results": []})
        await execute_aql(
            aql_query="RETURN 1",
            bind_vars=None,
            database_name=None,
            max_runtime=5.0,
        )

        call_args = mock_agent.arun.call_args[0][0]
        assert call_args["max_runtime"] == 5.0

    @pytest.mark.asyncio
    @patch("mcp_tools.aql_tools.aql_agent")
    async def test_explain_aql_query(self, mock_agent):
        from mcp_tools.aql_tools import explain_aql_query

        mock_agent.arun = AsyncMock(return_value={"plan": {}})
        result = await explain_aql_query(
            aql_query="FOR d IN col RETURN d",
            bind_vars=None,
            all_plans=True,
            max_plans=5,
            database_name="mydb",
        )

        mock_agent.arun.assert_called_once_with(
            {
                "operation": "explain",
                "aql_query": "FOR d IN col RETURN d",
                "bind_vars": {},
                "database_name": "mydb",
                "all_plans": True,
                "max_plans": 5,
            }
        )
        assert result == {"plan": {}}


# ---------------------------------------------------------------------------
# document_tools
# ---------------------------------------------------------------------------


class TestDocumentTools:
    @pytest.mark.asyncio
    @patch("mcp_tools.document_tools.doc_agent")
    async def test_create_document(self, mock_agent):
        from mcp_tools.document_tools import create_document

        mock_agent.arun = AsyncMock(return_value={"_key": "123"})
        result = await create_document(
            collection_name="users",
            document_data={"name": "Alice"},
            database_name=None,
        )

        mock_agent.arun.assert_called_once_with(
            {
                "operation": "create_document",
                "database_name": None,
                "collection_name": "users",
                "document_data": {"name": "Alice"},
            }
        )
        assert result == {"_key": "123"}

    @pytest.mark.asyncio
    @patch("mcp_tools.document_tools.doc_agent")
    async def test_read_documents_with_filter_defaults(self, mock_agent):
        from mcp_tools.document_tools import read_documents_with_filter

        mock_agent.arun = AsyncMock(return_value={"results": []})
        await read_documents_with_filter(
            collection_name="products",
            filters={"status": "active"},
            limit=100,
            skip=0,
            database_name=None,
        )

        mock_agent.arun.assert_called_once_with(
            {
                "operation": "read_documents_filter",
                "database_name": None,
                "collection_name": "products",
                "filters": {"status": "active"},
                "limit": 100,
                "skip": 0,
            }
        )

    @pytest.mark.asyncio
    @patch("mcp_tools.document_tools.doc_agent")
    async def test_delete_document(self, mock_agent):
        from mcp_tools.document_tools import delete_document

        mock_agent.arun = AsyncMock(return_value={"deleted": True})
        result = await delete_document(
            collection_name="users",
            document_key_or_id="user123",
            database_name="mydb",
        )

        mock_agent.arun.assert_called_once_with(
            {
                "operation": "delete_document",
                "database_name": "mydb",
                "collection_name": "users",
                "document_key_or_id": "user123",
            }
        )
        assert result == {"deleted": True}


# ---------------------------------------------------------------------------
# collection_tools
# ---------------------------------------------------------------------------


class TestCollectionTools:
    @pytest.mark.asyncio
    @patch("mcp_tools.collection_tools.collection_agent")
    async def test_list_collections(self, mock_agent):
        from mcp_tools.collection_tools import list_collections

        mock_agent.arun = AsyncMock(return_value={"collections": []})
        result = await list_collections(database_name="mydb")

        mock_agent.arun.assert_called_once_with(
            {"operation": "list_collections", "database_name": "mydb"}
        )
        assert result == {"collections": []}

    @pytest.mark.asyncio
    @patch("mcp_tools.collection_tools.collection_agent")
    async def test_create_collection_optional_sharding(self, mock_agent):
        from mcp_tools.collection_tools import create_collection

        mock_agent.arun = AsyncMock(return_value={"success": True})

        await create_collection(
            collection_name="orders",
            database_name="mydb",
            collection_type="document",
            number_of_shards=3,
            shard_keys=None,
            replication_factor=None,
            write_concern=None,
            sharding_strategy=None,
            computed_values=None,
        )

        call_args = mock_agent.arun.call_args[0][0]
        assert call_args["number_of_shards"] == 3
        assert "shard_keys" not in call_args
        assert "replication_factor" not in call_args
        assert "write_concern" not in call_args
        assert "sharding_strategy" not in call_args
        assert "computed_values" not in call_args
        assert call_args["operation"] == "create_collection"
        assert call_args["collection_name"] == "orders"


# ---------------------------------------------------------------------------
# user_tools
# ---------------------------------------------------------------------------


class TestUserTools:
    @pytest.mark.asyncio
    @patch("mcp_tools.user_tools.user_agent")
    async def test_create_user(self, mock_agent):
        from mcp_tools.user_tools import create_user

        mock_agent.arun = AsyncMock(return_value={"user": "alice"})
        result = await create_user(
            username="alice",
            password="secret",
            active=True,
            extra={"role": "admin"},
        )

        mock_agent.arun.assert_called_once_with(
            {
                "operation": "create_user",
                "username": "alice",
                "password": "secret",
                "active": True,
                "extra": {"role": "admin"},
            }
        )
        assert result == {"user": "alice"}

    @pytest.mark.asyncio
    @patch("mcp_tools.user_tools.user_agent")
    async def test_grant_permission(self, mock_agent):
        from mcp_tools.user_tools import grant_permission

        mock_agent.arun = AsyncMock(return_value={"granted": True})
        result = await grant_permission(
            username="alice",
            permission="rw",
            database_name="mydb",
            collection_name="users",
        )

        mock_agent.arun.assert_called_once_with(
            {
                "operation": "grant_permission",
                "username": "alice",
                "permission": "rw",
                "database_name": "mydb",
                "collection_name": "users",
            }
        )
        assert result == {"granted": True}
