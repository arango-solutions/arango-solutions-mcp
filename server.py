from mcp.server.fastmcp import FastMCP

from arango_connector import arango_db_lifespan
from config import settings

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

**CAPABILITIES (74 tools):**

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
mcp_app = FastMCP(name=_server_name, instructions=_server_instructions, lifespan=arango_db_lifespan)
# Import tool and resource modules to register them
# These imports MUST happen AFTER mcp_app is defined.
from mcp_tools import (  # noqa: F401, E402 — side-effect imports register MCP tools
    analyzer_tools,
    aql_tools,
    backup_tools,
    cluster_tools,
    collection_tools,
    database_tools,
    document_tools,
    graph_tools,
    index_tools,
    manual_tools,
    transaction_tools,
    traversal_tools,
    user_tools,
    vector_tools,
    view_tools,
)
