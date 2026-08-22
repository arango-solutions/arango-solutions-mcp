from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from arangodb_mcp.arango_connector import arango_db_lifespan
from arangodb_mcp.catalog.loader import load_tool_catalog
from arangodb_mcp.config import settings
from arangodb_mcp.policy.context import PolicyContext
from arangodb_mcp.policy.profiles import resolve_tool_inventory
from arangodb_mcp.policy.tool_manager import PolicyToolManager
from arangodb_mcp.protocol_compat import enable_mcp_2026_negotiation

MCP_2026_BRIDGE_ACTIVE = enable_mcp_2026_negotiation()

_tool_catalog = load_tool_catalog()
_policy_context = PolicyContext.from_settings(settings.server)
_profile_selection = resolve_tool_inventory(_tool_catalog, _policy_context)

# Explicitly define the server name and instructions
_server_name = settings.server.server_name
_server_instructions = f"""
ArangoDB MCP Server — comprehensive multi-model database operations.

**AQL WORKFLOW (MANDATORY for raw AQL queries):**
1. Call 'get-aql-manual' with manual_name="aql_ref" for syntax
2. Call 'get-aql-manual' with manual_name="optimization" for performance
3. Use 'validate-aql-query' to check syntax before execution
4. Use 'explain-aql-query' to verify index usage
5. Execute with 'execute-aql-query'

**CAPABILITIES ({len(_profile_selection.active_tools)} active of 81 cataloged tools):**
Active profile: `{_profile_selection.profile}`.
Additive toolsets: `{", ".join(sorted(_profile_selection.toolsets)) or "none"}`.

Document operations:
  create/read/update/delete/replace documents, bulk operations, upsert

Collection management:
  create (with sharding, replication, computed values), list, delete, properties

Database management:
  create, list, delete, info

Graph management:
  create named graphs (standard, SmartGraph, SatelliteGraph), edges, properties
  Graph traversals: traverse, shortest-path, k-shortest-paths, neighbors

AQL query engine:
  execute, explain (plan analysis), validate (syntax check)

Index management:
  create (persistent, inverted, geo, ttl, vector/ANN, mdi), list, delete

Vector / semantic search (3.12.4+):
  vector-search (ANN with cosine/l2/innerProduct), hybrid-search (vector + BM25)

Search views:
  ArangoSearch and search-alias views — create, update, replace, delete

Analyzers:
  create, list, delete, properties

Cluster administration:
  health, server role/count/endpoints/statistics, shard imbalance,
  rebalance, maintenance mode, collection shard distribution

Stream transactions:
  begin, status, commit, abort, list running transactions,
  execute server-side JS transactions — for multi-document ACID atomicity

Hot backup (Enterprise Edition):
  create, list, restore, delete — point-in-time deployment snapshots

User & permission management:
  list/get/create/update/delete users, list/get/grant/revoke permissions
  at database and collection level (rw, ro, none)

Embeddings & shared-memory patterns:
  embed-text, embed-document — OpenAI embeddings (requires OPENAI_API_KEY)
  pattern-search (hybrid vector + BM25), save-pattern, pattern-index,
  pattern-applied, save-drift-alert — cross-project pattern & PRD-drift memory

**Default database:** '{settings.arango.default_db_name}'
All operations accept an optional database_name parameter.

**Best practices:**
- Consult AQL manuals before writing raw queries
- Use 'explain-aql-query' to verify index usage before executing
- Use dedicated graph traversal tools instead of hand-writing traversal AQL
- Use 'vector-search' instead of writing APPROX_NEAR_* AQL manually
- Create indexes on frequently filtered/sorted fields
- In clusters: choose shard keys matching query patterns
- Use stream transactions for multi-document atomicity
- Hot backup operations require Enterprise Edition
"""
# Create the FastMCP application instance
_allowed_hosts = [
    item.strip() for item in settings.server.mcp_allowed_hosts.split(",") if item.strip()
]
_allowed_origins = [
    item.strip() for item in settings.server.mcp_allowed_origins.split(",") if item.strip()
]
_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=settings.server.mcp_dns_rebinding_protection,
    allowed_hosts=_allowed_hosts,
    allowed_origins=_allowed_origins,
)
mcp_app = FastMCP(
    name=_server_name,
    instructions=_server_instructions,
    host=settings.server.mcp_host,
    port=settings.server.mcp_port,
    json_response=True,
    stateless_http=settings.server.mcp_protocol_mode != "legacy",
    transport_security=_transport_security,
    lifespan=arango_db_lifespan,
)
mcp_app._tool_manager = PolicyToolManager(
    catalog=_tool_catalog,
    selection=_profile_selection,
    result_contract=_policy_context.result_contract,
    confirmation_secret=(
        settings.server.mcp_confirmation_secret.get_secret_value()
        if settings.server.mcp_confirmation_secret is not None
        else None
    ),
    warn_on_duplicate_tools=mcp_app.settings.warn_on_duplicate_tools,
)
# Import tool and resource modules to register them
# These imports MUST happen AFTER mcp_app is defined.
from arangodb_mcp.mcp_tools import (  # noqa: F401, E402 — side-effect imports register MCP tools
    analyzer_tools,
    aql_tools,
    backup_tools,
    cluster_tools,
    collection_tools,
    database_tools,
    document_tools,
    embedding_tools,
    graph_tools,
    index_tools,
    manual_tools,
    pattern_memory_tools,
    transaction_tools,
    traversal_tools,
    user_tools,
    vector_tools,
    view_tools,
)

mcp_app._tool_manager.finalize_registration()

import arangodb_mcp.mcp_content as _mcp_content  # noqa: E402, F401 — registers resources and prompts
