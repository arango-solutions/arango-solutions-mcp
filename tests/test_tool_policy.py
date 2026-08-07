"""Contract tests for the canonical catalog and startup tool policy."""

import json
import os
from unittest.mock import patch

import pytest
from mcp.server.fastmcp.exceptions import ToolError

os.environ.setdefault("ARANGO_HOSTS", "http://localhost:8529")
os.environ.setdefault("ARANGO_ROOT_USERNAME", "root")
os.environ.setdefault("ARANGO_ROOT_PASSWORD", "test")

with patch("arangodb_mcp.arango_connector.ArangoClient"):
    from arangodb_mcp.server import mcp_app

from arangodb_mcp.catalog.loader import CatalogError, load_tool_catalog
from arangodb_mcp.policy.actor_context import ArangoCredentials, RequestIdentity, identity_scope
from arangodb_mcp.policy.context import PolicyContext
from arangodb_mcp.policy.profiles import resolve_tool_inventory
from arangodb_mcp.policy.tool_manager import PolicyToolManager


def _names(value: str) -> frozenset[str]:
    return frozenset(value.split())


EXPECTED_INVENTORIES = {
    "readonly": _names(
        """
        cluster-calculate-imbalance cluster-endpoints cluster-health cluster-server-count
        cluster-server-role cluster-server-statistics collection-shard-distribution
        explain-aql-query get-aql-manual get-collection-properties get-database-info
        list-collections list-databases list-indexes read-document
        read-documents-with-filter validate-aql-query
        """
    ),
    "developer": _names(
        """
        abort-transaction begin-transaction cluster-calculate-imbalance cluster-endpoints
        cluster-health cluster-server-count cluster-server-role cluster-server-statistics
        collection-shard-distribution commit-transaction create-collection create-document
        create-documents-bulk create-index delete-document delete-documents-bulk delete-index
        execute-aql-query explain-aql-query get-aql-manual get-collection-properties
        get-database-info list-collections list-databases list-indexes list-transactions
        pattern-applied pattern-index pattern-search read-document read-documents-with-filter
        replace-document save-drift-alert save-pattern transaction-status update-document
        update-documents-bulk upsert-document validate-aql-query
        """
    ),
    "operator": _names(
        """
        abort-transaction begin-transaction cluster-calculate-imbalance cluster-endpoints
        cluster-health cluster-rebalance cluster-server-count cluster-server-role
        cluster-server-statistics cluster-toggle-maintenance collection-shard-distribution
        commit-transaction create-backup create-collection create-database create-document
        create-documents-bulk create-index delete-backup delete-collection delete-database
        delete-document delete-documents-bulk delete-index execute-aql-query
        execute-transaction explain-aql-query get-aql-manual get-collection-properties
        get-database-info list-backups list-collections list-databases list-indexes
        list-transactions pattern-applied pattern-index pattern-search read-document
        read-documents-with-filter replace-document restore-backup save-drift-alert save-pattern
        transaction-status update-document update-documents-bulk upsert-document
        validate-aql-query
        """
    ),
    "admin": _names(
        """
        abort-transaction begin-transaction cluster-calculate-imbalance cluster-endpoints
        cluster-health cluster-rebalance cluster-server-count cluster-server-role
        cluster-server-statistics cluster-toggle-maintenance collection-shard-distribution
        commit-transaction create-analyzer create-backup create-collection create-database
        create-document create-documents-bulk create-edge create-graph create-index create-user
        create-view delete-analyzer delete-backup delete-collection delete-database
        delete-document delete-documents-bulk delete-graph delete-index delete-user delete-view
        embed-document embed-text execute-aql-query execute-transaction explain-aql-query
        get-analyzer-properties get-aql-manual get-collection-properties get-database-info
        get-graph-properties get-permission get-user get-view-properties grant-permission
        graph-k-shortest-paths graph-neighbors graph-shortest-path graph-traverse hybrid-search
        list-analyzers list-backups list-collections list-databases list-graphs list-indexes
        list-permissions list-transactions list-users list-views pattern-applied pattern-index
        pattern-search read-document read-documents-with-filter replace-document
        replace-view-properties restore-backup revoke-permission save-drift-alert save-pattern
        transaction-status update-document update-documents-bulk update-user
        update-view-properties upsert-document validate-aql-query vector-search
        """
    ),
}


def _context(
    profile: str,
    *,
    toolsets: frozenset[str] = frozenset(),
    denied_tools: frozenset[str] = frozenset(),
    denied_categories: frozenset[str] = frozenset(),
) -> PolicyContext:
    return PolicyContext(
        profile=profile,
        toolsets=toolsets,
        denied_tools=denied_tools,
        denied_categories=denied_categories,
        result_contract="v3",
    )


def test_catalog_covers_every_registered_tool_exactly_once():
    catalog = load_tool_catalog()
    manager = mcp_app._tool_manager
    assert len(catalog.tools) == 81
    assert len(manager.all_registered_tools()) == 81
    catalog.validate_registered(tool.name for tool in manager.all_registered_tools())
    assert all(tool.limits.max_runtime_ms > 0 for tool in catalog.tools.values())


@pytest.mark.parametrize("profile", ["readonly", "developer", "operator", "admin"])
def test_exact_inventory_for_each_base_profile(profile):
    selection = resolve_tool_inventory(load_tool_catalog(), _context(profile))
    assert selection.active_tools == EXPECTED_INVENTORIES[profile]


def test_graph_and_search_are_additive_without_bypassing_readonly():
    catalog = load_tool_catalog()
    base = resolve_tool_inventory(catalog, _context("readonly")).active_tools
    graph = resolve_tool_inventory(
        catalog, _context("readonly", toolsets=frozenset({"graph"}))
    ).active_tools
    search = resolve_tool_inventory(
        catalog, _context("readonly", toolsets=frozenset({"search"}))
    ).active_tools
    assert graph - base == _names(
        """
        list-graphs get-graph-properties graph-traverse graph-shortest-path
        graph-k-shortest-paths graph-neighbors
        """
    )
    assert search - base == _names(
        """
        list-analyzers get-analyzer-properties embed-text embed-document vector-search
        hybrid-search list-views get-view-properties
        """
    )
    assert all(catalog.get(name).operation == "read" for name in graph | search)


def test_denylists_remove_tools_and_categories_and_fail_on_typos():
    catalog = load_tool_catalog()
    selection = resolve_tool_inventory(
        catalog,
        _context(
            "readonly",
            denied_tools=frozenset({"list-databases"}),
            denied_categories=frozenset({"cluster"}),
        ),
    )
    assert "list-databases" not in selection.active_tools
    assert all(catalog.get(name).category != "cluster" for name in selection.active_tools)

    with pytest.raises(ValueError, match="Unknown denied MCP tools"):
        resolve_tool_inventory(catalog, _context("readonly", denied_tools=frozenset({"typo-tool"})))
    with pytest.raises(ValueError, match="Unknown denied MCP categories"):
        resolve_tool_inventory(
            catalog, _context("readonly", denied_categories=frozenset({"typo-category"}))
        )


@pytest.mark.asyncio
async def test_denied_tool_never_registers_or_executes():
    catalog = load_tool_catalog()
    selection = resolve_tool_inventory(
        catalog, _context("readonly", denied_tools=frozenset({"list-databases"}))
    )
    manager = PolicyToolManager(catalog=catalog, selection=selection, result_contract="v3")

    async def list_databases():
        return {"databases": []}

    manager.add_tool(list_databases, name="list-databases")
    assert manager.list_tools() == []
    with pytest.raises(ToolError, match="unavailable under the active MCP policy"):
        await manager.call_tool("list-databases", {})


def test_unknown_tool_fails_registration():
    catalog = load_tool_catalog()
    manager = PolicyToolManager(
        catalog=catalog,
        selection=resolve_tool_inventory(catalog, _context("admin")),
        result_contract="v3",
    )

    async def unknown_tool():
        return {}

    with pytest.raises(CatalogError, match="not present"):
        manager.add_tool(unknown_tool, name="unknown-tool")


@pytest.mark.asyncio
async def test_default_tools_list_has_bounded_token_footprint():
    tools = await mcp_app.list_tools()
    payload = json.dumps(
        [tool.model_dump(mode="json", by_alias=True, exclude_none=True) for tool in tools],
        separators=(",", ":"),
    )
    estimated_tokens = (len(payload) + 3) // 4
    assert {tool.name for tool in tools} == EXPECTED_INVENTORIES["readonly"]
    assert estimated_tokens <= 9000


def _identity(
    scopes: frozenset[str],
    databases: frozenset[str] = frozenset({"tenant_a"}),
) -> RequestIdentity:
    return RequestIdentity(
        actor_id="alice",
        issuer="https://issuer.example",
        subject="alice",
        oauth_scopes=scopes,
        databases=databases,
        credentials=ArangoCredentials(
            username="alice-db",
            password="server-secret",
            databases=databases,
        ),
    )


def test_visible_tools_intersect_startup_profile_and_oauth_operation_scopes():
    catalog = load_tool_catalog()
    readonly = PolicyToolManager(
        catalog=catalog,
        selection=resolve_tool_inventory(catalog, _context("readonly")),
        result_contract="v3",
    )

    async def list_databases():
        return {"databases": []}

    readonly.add_tool(list_databases, name="list-databases")
    with identity_scope(_identity(frozenset({"mcp:admin"}), frozenset({"_system"}))):
        assert readonly.list_tools() == []

    with identity_scope(_identity(frozenset({"mcp:read"}), frozenset({"_system"}))):
        assert [tool.name for tool in readonly.list_tools()] == ["list-databases"]


@pytest.mark.asyncio
async def test_dispatch_denies_missing_operation_scope_with_structured_error():
    catalog = load_tool_catalog()
    manager = PolicyToolManager(
        catalog=catalog,
        selection=resolve_tool_inventory(catalog, _context("developer")),
        result_contract="v3",
    )
    executed = False

    async def create_collection():
        nonlocal executed
        executed = True
        return {"created": True}

    manager.add_tool(create_collection, name="create-collection")
    with identity_scope(_identity(frozenset({"mcp:read"}))):
        result = await manager.call_tool("create-collection", {})

    assert result["error"]["code"] == "insufficient_scope"
    assert executed is False


@pytest.mark.asyncio
async def test_dispatch_denies_database_outside_effective_allowlist():
    catalog = load_tool_catalog()
    manager = PolicyToolManager(
        catalog=catalog,
        selection=resolve_tool_inventory(catalog, _context("readonly")),
        result_contract="v3",
    )
    executed = False

    async def get_database_info(database_name=None):
        nonlocal executed
        executed = True
        return {"database": database_name}

    manager.add_tool(get_database_info, name="get-database-info")
    with identity_scope(_identity(frozenset({"mcp:read"}))):
        result = await manager.call_tool(
            "get-database-info",
            {"database_name": "tenant_b"},
        )

    assert result["error"]["code"] == "database_access_denied"
    assert executed is False
