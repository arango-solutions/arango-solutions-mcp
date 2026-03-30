# ArangoDB MCP Server

A comprehensive [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server for ArangoDB, providing **74 tools** covering document CRUD, graph traversals, AQL queries, vector/semantic search, cluster administration, stream transactions, hot backup, user/permission management, and more.

Built for AI assistants (Cursor, Claude Desktop, etc.) that need full-spectrum access to ArangoDB's multi-model capabilities.

## Supported ArangoDB Versions

- **ArangoDB 3.12+** (vector search requires 3.12.4+ with `--vector-index`)
- **ArangoDB 4.0** (under development — forward-compatible)

## Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management
- ArangoDB instance (local, Docker, or remote)

## Quick Start

### 1. Install

```bash
git clone https://github.com/arango-solutions/arango-solutions-mcp.git
cd arango-solutions-mcp
poetry install
```

### 2. Configure Your MCP Client

**Cursor IDE** — edit `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "arangodb-mcp": {
      "command": "poetry",
      "args": ["run", "python", "main.py"],
      "cwd": "/path/to/arango-mcp-server",
      "env": {
        "ARANGO_HOSTS": "http://localhost:8529",
        "ARANGO_ROOT_USERNAME": "root",
        "ARANGO_ROOT_PASSWORD": "your_password_here",
        "ARANGO_DEFAULT_DB_NAME": "myapp"
      }
    }
  }
}
```

**Claude Desktop** — edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "arangodb-mcp": {
      "command": "poetry",
      "args": ["run", "python", "main.py"],
      "cwd": "/path/to/arango-mcp-server",
      "env": {
        "ARANGO_HOSTS": "http://localhost:8529",
        "ARANGO_ROOT_USERNAME": "root",
        "ARANGO_ROOT_PASSWORD": "your_password_here",
        "ARANGO_DEFAULT_DB_NAME": "myapp"
      }
    }
  }
}
```

### 3. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ARANGO_HOSTS` | Yes | — | ArangoDB server URL(s) |
| `ARANGO_ROOT_USERNAME` | Yes | — | ArangoDB username |
| `ARANGO_ROOT_PASSWORD` | Yes | — | ArangoDB password |
| `ARANGO_DEFAULT_DB_NAME` | No | `_system` | Default database name |
| `ARANGO_VERIFY_SSL` | No | `true` | Verify SSL certificates |
| `ARANGO_SSL_CERT_PATH` | No | — | Path to SSL certificate file |
| `LOG_LEVEL` | No | `INFO` | Server log level |
| `ENABLE_JS_TRANSACTIONS` | No | `false` | Enable server-side JavaScript transactions (security-sensitive) |

All tools accept an optional `database_name` parameter to override the default.

---

## Tools (74)

### Document Operations (10)

| Tool | Description |
|------|-------------|
| `create-document` | Insert a single document |
| `create-documents-bulk` | Bulk insert an array of documents |
| `read-document` | Get a document by key or ID |
| `read-documents-with-filter` | Query documents with filters, pagination |
| `update-document` | Partial update by key |
| `delete-document` | Remove a document by key |
| `replace-document` | Full document replacement |
| `upsert-document` | Insert or update based on search criteria |
| `update-documents-bulk` | Bulk partial updates via AQL |
| `delete-documents-bulk` | Bulk deletes via AQL filter |

### Collection Management (4)

| Tool | Description |
|------|-------------|
| `list-collections` | List all collections in a database |
| `create-collection` | Create document/edge collections (with sharding, replication, computed values) |
| `delete-collection` | Drop a collection |
| `get-collection-properties` | Collection stats, shard config, key type |

### Database Management (4)

| Tool | Description |
|------|-------------|
| `list-databases` | List all databases |
| `create-database` | Create a new database |
| `delete-database` | Drop a database |
| `get-database-info` | Database properties and stats |

### Graph Management (5)

| Tool | Description |
|------|-------------|
| `list-graphs` | List named graphs |
| `create-graph` | Create graphs (standard, SmartGraph, SatelliteGraph, EnterpriseGraph) |
| `delete-graph` | Drop a graph (optionally drop collections) |
| `create-edge` | Insert an edge between two vertices |
| `get-graph-properties` | Edge definitions, orphan collections, cluster config |

### Graph Traversals (4)

| Tool | Description |
|------|-------------|
| `graph-traverse` | Multi-depth traversal with vertex/edge filters, path return |
| `graph-shortest-path` | Single shortest path (optionally weighted) |
| `graph-k-shortest-paths` | K alternative shortest paths |
| `graph-neighbors` | Deduplicated neighbor discovery at a given depth |

### AQL Query Engine (3)

| Tool | Description |
|------|-------------|
| `execute-aql-query` | Execute AQL with bind variables, stats |
| `explain-aql-query` | Execution plan analysis (indexes, costs, optimizer rules) |
| `validate-aql-query` | Syntax check without execution |

### Index Management (3)

| Tool | Description |
|------|-------------|
| `list-indexes` | List indexes on a collection |
| `create-index` | Create persistent, inverted, geo, TTL, vector (ANN), MDI indexes |
| `delete-index` | Remove an index by ID |

### Vector & Semantic Search (2)

*Requires ArangoDB 3.12.4+ with `--vector-index` enabled.*

| Tool | Description |
|------|-------------|
| `vector-search` | Approximate nearest-neighbor search (cosine, L2, inner product) |
| `hybrid-search` | Combined vector + BM25 text search with weighted fusion |

### Search Views (6)

| Tool | Description |
|------|-------------|
| `list-views` | List ArangoSearch / search-alias views |
| `create-view` | Create an ArangoSearch or search-alias view |
| `get-view-properties` | View configuration details |
| `update-view-properties` | Modify view settings (partial) |
| `replace-view-properties` | Replace view configuration |
| `delete-view` | Drop a view |

### Analyzers (4)

| Tool | Description |
|------|-------------|
| `list-analyzers` | List text analyzers |
| `create-analyzer` | Create a custom analyzer (text, ngram, stem, etc.) |
| `delete-analyzer` | Remove an analyzer |
| `get-analyzer-properties` | Analyzer type and configuration |

### Cluster Administration (9)

| Tool | Description |
|------|-------------|
| `cluster-health` | Overall cluster health status |
| `cluster-server-role` | Role of the connected server (Coordinator, DBServer, Single) |
| `cluster-server-count` | Number of coordinators + DB servers |
| `cluster-endpoints` | List all coordinator endpoints |
| `cluster-server-statistics` | CPU, memory, request stats for a server |
| `cluster-calculate-imbalance` | Shard distribution imbalance report |
| `cluster-rebalance` | Trigger automatic shard rebalancing |
| `cluster-toggle-maintenance` | Enable/disable cluster maintenance mode |
| `collection-shard-distribution` | Shard → server mapping for a collection |

### Stream Transactions (6)

| Tool | Description |
|------|-------------|
| `begin-transaction` | Start a stream transaction (declare read/write/exclusive collections) |
| `transaction-status` | Check if a transaction is running, committed, or aborted |
| `commit-transaction` | Commit and persist all changes |
| `abort-transaction` | Roll back all changes |
| `list-transactions` | List currently running stream transactions |
| `execute-transaction` | Execute a server-side JS transaction atomically (**disabled by default** — set `ENABLE_JS_TRANSACTIONS=true`) |

### Hot Backup (4) — Enterprise Edition

| Tool | Description |
|------|-------------|
| `create-backup` | Create a point-in-time hot backup of the deployment |
| `list-backups` | List available backups |
| `restore-backup` | Restore from a backup (server restarts) |
| `delete-backup` | Permanently remove a backup |

### User & Permission Management (9)

| Tool | Description |
|------|-------------|
| `list-users` | List all server users |
| `get-user` | Get user details and metadata |
| `create-user` | Create a new user with password, active flag, extra data |
| `update-user` | Update password, active status, or metadata |
| `delete-user` | Remove a user and all permission grants |
| `list-permissions` | All database/collection permission grants for a user |
| `get-permission` | Effective permission level on a database or collection |
| `grant-permission` | Grant rw/ro/none access at database or collection level |
| `revoke-permission` | Remove a permission grant (falls back to parent level) |

### AQL Reference (1)

| Tool | Description |
|------|-------------|
| `get-aql-manual` | Retrieve AQL syntax, optimization, or Cypher→AQL migration guides |

---

## Architecture

```
arango-mcp-server/
├── main.py                  # Entry point, event loop setup
├── server.py                # FastMCP app, server instructions
├── config.py                # Pydantic settings (env-based, zero hardcoding)
├── arango_connector.py      # Connection pool, SSL, lifespan management
│
├── agents/                  # Business logic layer
│   ├── agent_base.py                    # Abstract base class
│   ├── database_management_agent.py     # DB create/list/delete
│   ├── collection_management_agent.py   # Collections + sharding config
│   ├── document_crud_agent.py           # Full document lifecycle
│   ├── graph_management_agent.py        # Named graphs, SmartGraphs
│   ├── graph_traversal_agent.py         # Traversals, shortest paths
│   ├── aql_execution_agent.py           # Execute, explain, validate AQL
│   ├── index_management_agent.py        # All index types incl. vector
│   ├── vector_search_agent.py           # ANN search, hybrid search
│   ├── view_management_agent.py         # ArangoSearch, search-alias views
│   ├── analyzer_management_agent.py     # Text analyzers
│   ├── cluster_management_agent.py      # Cluster health, shards, rebalance
│   ├── transaction_management_agent.py  # Stream transactions
│   ├── backup_management_agent.py       # Hot backups (Enterprise)
│   ├── user_management_agent.py         # Users and permissions
│   └── manual_management_agent.py       # AQL reference manuals
│
├── mcp_tools/               # MCP tool definitions (thin wrappers → agents)
│   ├── database_tools.py
│   ├── collection_tools.py
│   ├── document_tools.py
│   ├── graph_tools.py
│   ├── traversal_tools.py
│   ├── aql_tools.py
│   ├── index_tools.py
│   ├── vector_tools.py
│   ├── view_tools.py
│   ├── analyzer_tools.py
│   ├── cluster_tools.py
│   ├── transaction_tools.py
│   ├── backup_tools.py
│   ├── user_tools.py
│   └── manual_tools.py
│
├── tests/                   # Pytest suite (223 tests)
│   ├── conftest.py          # Auto-provisions Docker containers
│   ├── test_connectivity.py
│   ├── test_agents.py
│   ├── test_aql_utils.py
│   ├── test_database_manual_analyzer.py
│   ├── test_vector_search.py
│   ├── test_traversal.py
│   ├── test_transactions.py
│   ├── test_users.py
│   └── test_cluster.py
│
└── manuals/                 # AQL reference documents
```

The codebase follows a two-layer pattern:

- **MCP Tools** (`mcp_tools/`) — thin FastMCP-decorated functions that validate inputs and delegate to agents.
- **Agents** (`agents/`) — business logic classes inheriting from `ArangoAgentBase` that interact with ArangoDB via `python-arango`.

---

## Development

### Running Tests

Tests automatically spin up a Docker container with ArangoDB on a random port, run the suite, and tear it down:

```bash
poetry install --with dev
poetry run pytest tests/ -v --ignore=tests/test_cluster.py
```

To test against an existing ArangoDB instance (skips Docker):

```bash
ARANGO_HOSTS=http://localhost:8529 \
ARANGO_ROOT_PASSWORD=your_password \
  poetry run pytest tests/ -v
```

Cluster-specific tests require a multi-server deployment:

```bash
poetry run pytest tests/test_cluster.py -v
```

### Linting & Formatting

```bash
poetry run ruff check .         # lint
poetry run ruff format --check . # format check (use without --check to auto-fix)
poetry run mypy --ignore-missing-imports agents/ mcp_tools/ aql_utils.py config.py arango_connector.py server.py main.py
```

### Pre-commit Hooks

The project includes a `.pre-commit-config.yaml` for automated checks on commit:

```bash
pip install pre-commit
pre-commit install
```

### Adding a New Tool

1. Create an agent in `agents/` inheriting from `ArangoAgentBase`
2. Create tool definitions in `mcp_tools/` using `@mcp_app.tool`
3. Import the new tool module in `mcp_tools/__init__.py` and `server.py`
4. Add tests in `tests/`

---

## Security

| Feature | Description |
|---------|-------------|
| **Zero hardcoded credentials** | All connection parameters via `ARANGO_*` environment variables or `.env`; validated by Pydantic settings |
| **AQL injection prevention** | All identifiers validated by `aql_utils.py` before interpolation; all values use bind variables (`@param`) |
| **JS transaction gating** | `execute-transaction` disabled by default; requires explicit `ENABLE_JS_TRANSACTIONS=true` to enable arbitrary JS execution on the server |
| **SSL by default** | `ARANGO_VERIFY_SSL` defaults to `true`; optional `ARANGO_SSL_CERT_PATH` for custom certs |
| **Log redaction** | Bind variable values are never logged; only parameter keys appear in log output |
| **Destructive operation guards** | `_system` database deletion blocked at both tool and agent levels |

---

## Key Features

- **Zero hardcoded config** — all credentials via environment variables or `.env`
- **Multi-model coverage** — documents, graphs, search, vectors in one server
- **Cluster-aware** — sharding, replication, SmartGraphs, shard rebalancing
- **ACID transactions** — stream transactions for multi-document atomicity
- **Vector search** — approximate nearest-neighbor with cosine/L2/inner-product metrics
- **Hybrid search** — combine vector similarity with BM25 text relevance
- **AQL-first** — built-in manuals, explain plans, and syntax validation
- **Security by default** — AQL injection prevention, JS transaction gating, SSL verification, log redaction
- **Self-testing** — 223 automated tests with ephemeral Docker containers
- **Cross-platform** — runs on macOS, Linux, Windows (via Docker)

## License

See [LICENSE](LICENSE) for details.
