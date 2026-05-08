"""End-to-end tests for the MCP server framework layer.

These tests verify tool registration, schema validation, and server configuration
without requiring a running ArangoDB instance. They exercise the FastMCP framework
by importing the mcp_app and introspecting its tool registry directly.
"""

import os
import re

# Set required environment variables BEFORE any application imports.
# This prevents pydantic-settings from raising on missing ARANGO_* vars.
os.environ.setdefault("ARANGO_HOSTS", "http://localhost:8529")
os.environ.setdefault("ARANGO_ROOT_USERNAME", "root")
os.environ.setdefault("ARANGO_ROOT_PASSWORD", "test")
os.environ.setdefault("ARANGO_DEFAULT_DB_NAME", "_system")

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402

# Patch ArangoClient before server.py (transitively) tries to instantiate it
with patch("arango_connector.ArangoClient"):
    from server import mcp_app  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

CRITICAL_TOOLS = [
    "execute-aql-query",
    "create-document",
    "list-collections",
    "graph-traverse",
    "vector-search",
]


def _get_tools():
    return mcp_app._tool_manager.list_tools()


def _get_tool(name: str):
    tool = mcp_app._tool_manager.get_tool(name)
    assert tool is not None, f"Tool '{name}' not found in registry"
    return tool


# ===========================================================================
# 1. Tool Registration
# ===========================================================================


class TestToolRegistration:
    """Verify the MCP server registers the expected set of tools."""

    def test_all_74_tools_registered(self):
        tools = _get_tools()
        assert (
            len(tools) == 74
        ), f"Expected 74 tools, found {len(tools)}. Tool names: {sorted(t.name for t in tools)}"

    def test_tool_names_are_kebab_case(self):
        violations = [t.name for t in _get_tools() if not _KEBAB_RE.match(t.name)]
        assert violations == [], f"Non-kebab-case tool names: {violations}"

    @pytest.mark.parametrize("tool_name", CRITICAL_TOOLS)
    def test_critical_tools_exist(self, tool_name):
        names = {t.name for t in _get_tools()}
        assert (
            tool_name in names
        ), f"Critical tool '{tool_name}' missing. Registered: {sorted(names)}"


# ===========================================================================
# 2. Tool Schema Validation
# ===========================================================================


class TestToolSchemaValidation:
    """Verify tool parameter schemas match expectations."""

    def test_execute_aql_query_has_required_params(self):
        tool = _get_tool("execute-aql-query")
        required = tool.parameters.get("required", [])
        assert (
            "aql_query" in required
        ), f"'aql_query' should be required; required list is {required}"
        props = tool.parameters.get("properties", {})
        assert "aql_query" in props, "'aql_query' not in parameter properties"

    def test_create_document_schema(self):
        tool = _get_tool("create-document")
        required = tool.parameters.get("required", [])
        props = tool.parameters.get("properties", {})
        assert (
            "collection_name" in required
        ), f"'collection_name' should be required; got {required}"
        assert "document_data" in required, f"'document_data' should be required; got {required}"
        assert "collection_name" in props
        assert "document_data" in props

    def test_database_name_optional_on_most_tools(self):
        """database_name should have a default (i.e. not be required) on tools that accept it.

        A handful of tools legitimately require database_name (e.g. create-database,
        delete-database, permission tools that target a specific DB).
        """
        EXPECT_REQUIRED = {
            "create-database",
            "delete-database",
            "get-permission",
            "grant-permission",
            "revoke-permission",
        }
        tools_with_db = [
            t for t in _get_tools() if "database_name" in t.parameters.get("properties", {})
        ]
        assert len(tools_with_db) > 0, "No tools have a database_name parameter"

        violations = []
        for t in tools_with_db:
            if t.name in EXPECT_REQUIRED:
                continue
            required = t.parameters.get("required", [])
            if "database_name" in required:
                violations.append(t.name)

        assert (
            violations == []
        ), f"database_name should be optional but is required on: {violations}"


# ===========================================================================
# 3. Server Configuration
# ===========================================================================


class TestServerConfiguration:
    """Verify MCP server-level settings."""

    def test_server_name_from_config(self):
        from config import settings

        expected = settings.server.server_name
        actual = mcp_app._mcp_server.name
        assert actual == expected, f"Server name mismatch: {actual!r} != {expected!r}"

    def test_server_instructions_contain_tool_count(self):
        instructions = mcp_app._mcp_server.instructions
        assert instructions is not None, "Server instructions are None"
        assert "74 tools" in instructions, "'74 tools' not found in server instructions"
