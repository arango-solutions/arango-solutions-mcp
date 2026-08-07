"""MCP resources and safe workflow prompts."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

from arangodb_mcp.arango_connector import arango_connector
from arangodb_mcp.config import settings
from arangodb_mcp.policy.tool_manager import PolicyToolManager
from arangodb_mcp.server import MCP_2026_BRIDGE_ACTIVE, mcp_app

_MANUALS = {
    "aql_ref": Path(__file__).with_name("manuals") / "aql_ref.md",
    "optimization": Path(__file__).with_name("manuals") / "optimization.md",
    "cypher2aql": Path(__file__).with_name("manuals") / "cypher2aql.md",
}


@mcp_app.resource(
    "arangodb://manuals/{manual_name}",
    name="aql-manual",
    description="Version-controlled AQL syntax, optimization, and Cypher migration manuals.",
    mime_type="text/markdown",
)
def manual_resource(manual_name: str) -> str:
    try:
        path = _MANUALS[manual_name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown manual {manual_name!r}; expected one of {sorted(_MANUALS)}"
        ) from exc
    return path.read_text(encoding="utf-8")


@mcp_app.resource(
    "arangodb://schema",
    name="database-schema-summary",
    description="Bounded collection-level schema inventory for the configured database.",
    mime_type="application/json",
)
async def schema_resource() -> str:
    db = arango_connector.get_db()
    collections = await asyncio.to_thread(db.collections)
    if not isinstance(collections, list):
        raise RuntimeError("ArangoDB returned a non-materialized collection inventory")
    summary = [
        {
            "name": item.get("name"),
            "type": item.get("type"),
            "status": item.get("status"),
            "system": bool(item.get("isSystem", False)),
        }
        for item in collections[:1000]
    ]
    return json.dumps(
        {
            "database": db.name,
            "collections": summary,
            "truncated": len(collections) > 1000,
            "maximum": 1000,
        },
        sort_keys=True,
    )


@mcp_app.resource(
    "arangodb://profile",
    name="active-policy-profile",
    description="Active profile, additive toolsets, denylists, and exact tool inventory.",
    mime_type="application/json",
)
def profile_resource() -> str:
    manager = cast(PolicyToolManager, mcp_app._tool_manager)
    selection = manager.selection
    tools = sorted(tool.name for tool in manager.list_tools())
    return json.dumps(
        {
            "profile": selection.profile,
            "toolsets": sorted(selection.toolsets),
            "denied_tools": sorted(selection.denied_tools),
            "denied_categories": sorted(selection.denied_categories),
            "tool_count": len(tools),
            "tools": tools,
        },
        sort_keys=True,
    )


@mcp_app.resource(
    "arangodb://status",
    name="server-status",
    description="Non-secret protocol, policy, dependency, and contract status.",
    mime_type="application/json",
)
async def status_resource() -> str:
    healthy = await asyncio.to_thread(arango_connector.health_check)
    return json.dumps(
        {
            "server": settings.server.server_name,
            "version": settings.server.server_version,
            "protocol": "2026-07-28",
            "protocol_bridge_active": MCP_2026_BRIDGE_ACTIVE,
            "result_contract": settings.server.mcp_result_contract,
            "profile": settings.server.mcp_profile,
            "database": settings.arango.default_db_name,
            "database_ready": healthy,
        },
        sort_keys=True,
    )


@mcp_app.prompt(
    name="safe-aql-workflow",
    description="Plan a parser-validated, explained, bounded AQL operation.",
)
def safe_aql_workflow(task: str, database_name: str = "") -> str:
    target = database_name or settings.arango.default_db_name
    return f"""Safely complete this ArangoDB task against database {target!r}: {task}

1. Read arangodb://manuals/aql_ref and arangodb://manuals/optimization.
2. Draft one parameterized AQL query; never interpolate user values.
3. Call validate-aql-query, then explain-aql-query and inspect index use.
4. Prefer a read query. Mutations require an explicitly enabled profile and a trusted
   out-of-band confirmation bound to the final query and bind variables.
5. Execute with server-enforced runtime, row, byte, bulk, and concurrency ceilings.
"""


@mcp_app.prompt(
    name="safe-graph-workflow",
    description="Choose bounded graph tools before considering raw traversal AQL.",
)
def safe_graph_workflow(task: str, graph_name: str = "") -> str:
    graph = graph_name or "<select-from-list-graphs>"
    return f"""Safely complete this graph task: {task}

1. Confirm graph {graph!r} with list-graphs and get-graph-properties.
2. Prefer graph-neighbors, graph-traverse, or graph-shortest-path over raw AQL.
3. Use the smallest depth and result limit that satisfies the task.
4. Treat create/delete operations as explicit writes; irreversible actions require a
   trusted out-of-band confirmation token.
"""


@mcp_app.prompt(
    name="safe-search-workflow",
    description="Plan bounded ArangoSearch, vector, or hybrid retrieval.",
)
def safe_search_workflow(task: str, collection_name: str = "") -> str:
    collection = collection_name or "<select-from-list-collections>"
    return f"""Safely complete this search task over {collection!r}: {task}

1. Inspect collection, view, analyzer, and index metadata.
2. Choose vector-search for semantic nearest neighbors or hybrid-search for vector + BM25.
3. Keep top_k and response fields minimal and remain within the server ceilings.
4. Do not create or replace search infrastructure unless the active profile explicitly permits it.
"""


def registered_content_inventory() -> dict[str, list[str]]:
    """Return stable names for contract tests and status tooling."""
    resources = [str(resource.uri) for resource in mcp_app._resource_manager.list_resources()]
    templates = [template.uri_template for template in mcp_app._resource_manager.list_templates()]
    prompts: list[Any] = mcp_app._prompt_manager.list_prompts()
    return {
        "resources": sorted(resources),
        "templates": sorted(templates),
        "prompts": sorted(prompt.name for prompt in prompts),
    }
