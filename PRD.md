# Product Requirements Document — ArangoDB MCP Server

**Version:** 2.0.0
**Last Updated:** March 29, 2026
**Status:** Implemented
**Repository:** [arango-solutions/arango-solutions-mcp](https://github.com/arango-solutions/arango-solutions-mcp)

---

## 1. Overview

### 1.1 Product Summary

The ArangoDB MCP Server is a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that exposes **74 tools** giving AI assistants (Cursor, Claude Desktop, and any MCP-compatible client) comprehensive, programmatic access to ArangoDB's multi-model database capabilities. It bridges the gap between natural-language AI interactions and ArangoDB's document, graph, search, and cluster features — enabling AI agents to build, query, manage, and administer ArangoDB deployments without hand-written driver code.

### 1.2 Problem Statement

AI coding assistants need structured access to databases to be effective. Without an MCP integration, users must manually copy-paste queries, interpret raw API responses, and context-switch between the AI and database tooling. ArangoDB's multi-model nature (documents, graphs, search, vectors) amplifies this friction — each model has distinct query patterns, index types, and operational concerns.

### 1.3 Target Users

| Persona | Description |
|---------|-------------|
| **AI-assisted developer** | Uses Cursor, Claude Desktop, or similar to build applications backed by ArangoDB |
| **Data engineer** | Manages ArangoDB schemas, indexes, and cluster configuration through AI workflows |
| **Graph analyst** | Explores graph relationships, runs traversals, and shortest-path queries interactively |
| **DevOps / DBA** | Administers cluster health, shard rebalancing, backups, users, and permissions |

### 1.4 Design Principles

1. **Zero hardcoded secrets** — All credentials and connection parameters are injected via environment variables or `.env` files, never stored in code.
2. **Multi-model first** — Every ArangoDB data model (document, graph, key-value, search, vector) is a first-class citizen with dedicated tools.
3. **Safety by default** — Destructive operations require explicit parameters; AQL identifier injection is prevented by validation; sensitive data is redacted from logs.
4. **AI-optimized ergonomics** — Tool descriptions, server instructions, and error messages are written for LLM consumption, not human CLI users.
5. **Thin tools, smart agents** — MCP tool definitions are thin Pydantic-validated wrappers; all business logic lives in testable agent classes.

---

## 2. Functional Requirements

### 2.1 Document Operations (10 tools)

Full document lifecycle management with single-document precision and bulk throughput.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| D-1 | `create-document` | Insert a single document into a collection | `collection_name`, `document_data`, `database_name` |
| D-2 | `create-documents-bulk` | Insert multiple documents in one operation | `collection_name`, `documents_data` (array) |
| D-3 | `read-document` | Retrieve a document by `_key` or `_id` | `collection_name`, `document_key_or_id` |
| D-4 | `read-documents-with-filter` | Query documents by filter criteria with pagination | `collection_name`, `filters`, `limit`, `skip` |
| D-5 | `update-document` | Partial merge update by `_key` | `collection_name`, `document_data` (must include `_key`) |
| D-6 | `delete-document` | Remove a single document | `collection_name`, `document_key_or_id` |
| D-7 | `replace-document` | Full document replacement by `_key` | `collection_name`, `document_data` |
| D-8 | `upsert-document` | Insert-or-update based on search criteria | `collection_name`, `search_fields`, `document_data`, `update_data` |
| D-9 | `update-documents-bulk` | Bulk partial updates | `collection_name`, `documents_data` |
| D-10 | `delete-documents-bulk` | Bulk deletes | `collection_name`, `documents_data` |

**Implementation:** `agents/document_crud_agent.py` → `mcp_tools/document_tools.py`

### 2.2 Collection Management (4 tools)

Create and manage document and edge collections with full cluster-aware configuration.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| C-1 | `list-collections` | List all user-defined collections in a database | `database_name` |
| C-2 | `create-collection` | Create document or edge collections | `collection_name`, `collection_type`, `number_of_shards`, `shard_keys`, `replication_factor`, `write_concern`, `sharding_strategy`, `computed_values` |
| C-3 | `delete-collection` | Drop a collection | `collection_name` |
| C-4 | `get-collection-properties` | Retrieve stats, shard config, revision, document count | `collection_name` |

**Implementation:** `agents/collection_management_agent.py` → `mcp_tools/collection_tools.py`

### 2.3 Database Management (4 tools)

Manage ArangoDB databases (requires `_system` database access).

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| DB-1 | `list-databases` | List all databases on the server | — |
| DB-2 | `create-database` | Create a new database | `database_name` |
| DB-3 | `delete-database` | Drop a database (blocks `_system` deletion) | `database_name` |
| DB-4 | `get-database-info` | Retrieve database properties | `database_name` |

**Implementation:** `agents/database_management_agent.py` → `mcp_tools/database_tools.py`

### 2.4 Graph Management (5 tools)

Manage named graphs including Enterprise features (SmartGraph, SatelliteGraph, EnterpriseGraph).

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| G-1 | `list-graphs` | List all named graphs | `database_name` |
| G-2 | `create-graph` | Create a named graph with edge definitions | `graph_name`, `edge_definitions`, `orphan_collections`, `smart`, `smart_field`, `shard_count`, `replication_factor`, `is_satellite` |
| G-3 | `delete-graph` | Drop a graph (optionally its collections) | `graph_name`, `drop_collections` |
| G-4 | `create-edge` | Insert an edge between vertices within a graph | `graph_name`, `edge_collection_name`, `from_vertex_id`, `to_vertex_id`, `edge_data` |
| G-5 | `get-graph-properties` | Retrieve graph configuration and edge definitions | `graph_name` |

**Implementation:** `agents/graph_management_agent.py` → `mcp_tools/graph_tools.py`

### 2.5 Graph Traversals (4 tools)

AQL-backed traversal queries with automatic query generation.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| T-1 | `graph-traverse` | Multi-depth traversal with filtering | `start_vertex`, `direction`, `min_depth`, `max_depth`, `graph_name` or `edge_collections`, `vertex_filters`, `edge_filters`, `return_vertices`, `return_edges`, `return_paths` |
| T-2 | `graph-shortest-path` | Single shortest path (optionally weighted) | `start_vertex`, `target_vertex`, `graph_name`, `weight_attribute` |
| T-3 | `graph-k-shortest-paths` | K alternative shortest paths | `start_vertex`, `target_vertex`, `limit` |
| T-4 | `graph-neighbors` | Deduplicated neighbor discovery at a given depth | `start_vertex`, `depth`, `deduplicate` |

**Implementation:** `agents/graph_traversal_agent.py` → `mcp_tools/traversal_tools.py`

### 2.6 AQL Query Engine (3 tools)

Direct AQL execution with plan analysis and syntax validation.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| Q-1 | `execute-aql-query` | Execute AQL with bind variables; returns results, stats, and counts | `aql_query`, `bind_vars`, `database_name` |
| Q-2 | `explain-aql-query` | Execution plan analysis (indexes, costs, optimizer rules) | `aql_query`, `bind_vars`, `all_plans`, `max_plans`, `opt_rules` |
| Q-3 | `validate-aql-query` | Syntax check without execution | `aql_query` |

**Implementation:** `agents/aql_execution_agent.py` → `mcp_tools/aql_tools.py`

### 2.7 Index Management (3 tools)

Create and manage all ArangoDB index types including vector and MDI.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| I-1 | `list-indexes` | List all indexes on a collection | `collection_name` |
| I-2 | `create-index` | Create any index type | `collection_name`, `index_definition` (type, fields, params) |
| I-3 | `delete-index` | Remove an index (blocks primary index deletion) | `collection_name`, `index_id_or_name` |

**Supported index types:** `persistent`, `inverted`, `geo`, `ttl`, `fulltext`, `mdi`, `mdi-prefixed`, `vector`

**Implementation:** `agents/index_management_agent.py` → `mcp_tools/index_tools.py`

### 2.8 Vector & Semantic Search (2 tools)

Approximate nearest-neighbor and hybrid search. Requires ArangoDB 3.12.4+ with `--vector-index`.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| V-1 | `vector-search` | ANN search using `APPROX_NEAR_*` functions | `collection_name`, `vector_field`, `query_vector`, `metric` (cosine/l2/innerProduct), `limit`, `n_probe`, `return_fields`, `filters` |
| V-2 | `hybrid-search` | Combined vector similarity + BM25 text search with weighted fusion | `collection_name`, `vector_field`, `query_vector`, `view_name`, `text_field`, `text_query`, `text_analyzer`, `vector_weight`, `text_weight` |

**Implementation:** `agents/vector_search_agent.py` → `mcp_tools/vector_tools.py`

### 2.9 Search Views (6 tools)

Manage ArangoSearch and search-alias views for full-text and multi-attribute search.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| SV-1 | `list-views` | List all views in a database | `database_name` |
| SV-2 | `create-view` | Create ArangoSearch or search-alias view | `view_name`, `view_type`, `properties` |
| SV-3 | `get-view-properties` | Retrieve view configuration | `view_name` |
| SV-4 | `update-view-properties` | Partial view configuration update | `view_name`, `properties` |
| SV-5 | `replace-view-properties` | Full view configuration replacement | `view_name`, `properties` |
| SV-6 | `delete-view` | Drop a view | `view_name` |

**Implementation:** `agents/view_management_agent.py` → `mcp_tools/view_tools.py`

### 2.10 Analyzers (4 tools)

Manage text analyzers for ArangoSearch.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| A-1 | `list-analyzers` | List all analyzers in a database | `database_name` |
| A-2 | `create-analyzer` | Create a custom analyzer | `analyzer_name`, `analyzer_type`, `properties`, `features` |
| A-3 | `delete-analyzer` | Remove an analyzer | `analyzer_name` |
| A-4 | `get-analyzer-properties` | Retrieve analyzer definition | `analyzer_name` |

**Implementation:** `agents/analyzer_management_agent.py` → `mcp_tools/analyzer_tools.py`

### 2.11 Cluster Administration (9 tools)

Introspect and manage ArangoDB cluster deployments.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| CL-1 | `cluster-health` | Overall cluster health status | — |
| CL-2 | `cluster-server-role` | Role of the connected server (Coordinator/DBServer/Single) | — |
| CL-3 | `cluster-server-count` | Number of coordinators + DB servers | — |
| CL-4 | `cluster-endpoints` | List all coordinator endpoints | — |
| CL-5 | `cluster-server-statistics` | CPU, memory, request stats for a server | `server_id` |
| CL-6 | `cluster-calculate-imbalance` | Shard distribution imbalance report | — |
| CL-7 | `cluster-rebalance` | Trigger automatic shard rebalancing | `max_moves`, `move_leaders`, `move_followers` |
| CL-8 | `cluster-toggle-maintenance` | Enable/disable cluster maintenance mode | `mode` (on/off) |
| CL-9 | `collection-shard-distribution` | Shard → server mapping for a collection | `collection_name` |

**Implementation:** `agents/cluster_management_agent.py` → `mcp_tools/cluster_tools.py`

### 2.12 Stream Transactions (6 tools)

Multi-document ACID transactions with both stream and server-side JavaScript execution.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| TX-1 | `begin-transaction` | Start a stream transaction | `read`, `write`, `exclusive` (collection lists), `sync`, `lock_timeout`, `max_size` |
| TX-2 | `transaction-status` | Check transaction state | `transaction_id` |
| TX-3 | `commit-transaction` | Commit all changes | `transaction_id` |
| TX-4 | `abort-transaction` | Roll back all changes | `transaction_id` |
| TX-5 | `list-transactions` | List currently running transactions | — |
| TX-6 | `execute-transaction` | Execute server-side JS transaction (**disabled by default** — requires `ENABLE_JS_TRANSACTIONS=true`) | `command`, `params`, `read`, `write` |

**Implementation:** `agents/transaction_management_agent.py` → `mcp_tools/transaction_tools.py`

### 2.13 Hot Backup — Enterprise Edition (4 tools)

Point-in-time deployment snapshots. Requires ArangoDB Enterprise.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| BK-1 | `create-backup` | Create a hot backup | `label`, `allow_inconsistent`, `force`, `timeout` |
| BK-2 | `list-backups` | List available backups | `backup_id` (optional filter) |
| BK-3 | `restore-backup` | Restore from a backup | `backup_id` |
| BK-4 | `delete-backup` | Permanently remove a backup | `backup_id` |

**Implementation:** `agents/backup_management_agent.py` → `mcp_tools/backup_tools.py`

### 2.14 User & Permission Management (9 tools)

Manage server users and database/collection-level access control.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| U-1 | `list-users` | List all server users | — |
| U-2 | `get-user` | Get user details and metadata | `username` |
| U-3 | `create-user` | Create a new user | `username`, `password`, `active`, `extra` |
| U-4 | `update-user` | Update user properties | `username`, `password`, `active`, `extra` |
| U-5 | `delete-user` | Remove a user | `username` |
| U-6 | `list-permissions` | All permission grants for a user | `username` |
| U-7 | `get-permission` | Effective permission on a database/collection | `username`, `database`, `collection` |
| U-8 | `grant-permission` | Grant rw/ro/none access | `username`, `permission`, `database`, `collection` |
| U-9 | `revoke-permission` | Remove a permission grant | `username`, `database`, `collection` |

**Implementation:** `agents/user_management_agent.py` → `mcp_tools/user_tools.py`

### 2.15 AQL Reference (1 tool)

Serve built-in AQL documentation to the AI assistant.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| M-1 | `get-aql-manual` | Retrieve AQL syntax, optimization, or Cypher→AQL migration guides | `manual_name` (`aql_ref`, `optimization`, `cypher2aql`) |

**Implementation:** `agents/manual_management_agent.py` → `mcp_tools/manual_tools.py`

---

## 3. Non-Functional Requirements

### 3.1 Security

| Requirement | Implementation |
|-------------|----------------|
| **No hardcoded credentials** | All connection parameters via `ARANGO_*` environment variables; validated by Pydantic settings |
| **AQL injection prevention** | `aql_utils.py` validates all identifiers before AQL interpolation; values use bind variables (`@param`) |
| **Log redaction** | Bind variable values are never logged; only parameter keys appear in log output |
| **SSL/TLS by default** | `ARANGO_VERIFY_SSL` defaults to `true`; optional `ARANGO_SSL_CERT_PATH` with cross-platform path validation |
| **JS transaction gating** | `execute-transaction` disabled by default; requires `ENABLE_JS_TRANSACTIONS=true` to allow arbitrary JS execution on the server |
| **Defense-in-depth** | `_system` database deletion blocked at agent level (in addition to tool level) |

### 3.2 Reliability

| Requirement | Implementation |
|-------------|----------------|
| **Connection lifecycle** | Async context manager (`arango_db_lifespan`) connects on startup and disconnects in `finally` block |
| **Health checks** | `health_check()` probes the database with logged failures at WARNING level |
| **Graceful error handling** | `handle_arango_errors` decorator provides standardized error response format; specific ArangoDB exceptions caught before generic fallback |
| **Enterprise feature detection** | Backup agent detects non-Enterprise servers and returns clear error messages instead of stack traces |
| **Cluster-safe** | Cluster tools detect single-server deployments and return informative errors |

### 3.3 Performance

| Requirement | Implementation |
|-------------|----------------|
| **Connection pooling** | Configuration fields reserved (`max_connections`, `timeout`) for future `python-arango` pool tuning |
| **Cursor consumption** | All cursors fully iterated and results collected; no abandoned iterators |
| **Bind variables** | All AQL values passed as bind variables for server-side optimization |

### 3.4 Compatibility

| Requirement | Implementation |
|-------------|----------------|
| **ArangoDB versions** | 3.12+ (vector search requires 3.12.4+ with `--vector-index`); forward-compatible with 4.0 |
| **Python versions** | 3.10+ (uses `pyproject.toml` with `python = "^3.10"`) |
| **Platforms** | macOS, Linux, Windows — platform-specific event loop policies configured in `main.py` |
| **MCP clients** | Any MCP-compatible client (Cursor IDE, Claude Desktop, custom integrations) |
| **Transport** | stdio transport (standard for MCP) |

### 3.5 Observability

| Requirement | Implementation |
|-------------|----------------|
| **Structured logging** | All agents use `logging.getLogger(__name__)`; log level configurable via `LOG_LEVEL` env var |
| **Startup diagnostics** | Server logs platform, Python version, server version, default database on startup |
| **Error context** | Error responses include `error` message, optional `error_code`, and agent-specific context |
| **Metrics** | `enable_metrics` configuration field reserved for future implementation |

---

## 4. Architecture

### 4.1 System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   MCP Client                        │
│         (Cursor IDE / Claude Desktop)               │
└──────────────────────┬──────────────────────────────┘
                       │ stdio (JSON-RPC)
┌──────────────────────▼──────────────────────────────┐
│                 FastMCP Server                       │
│                  (server.py)                         │
│  ┌───────────────────────────────────────────────┐  │
│  │              mcp_tools/*.py                   │  │
│  │   74 @mcp_app.tool decorated functions        │  │
│  │   Pydantic Field validation + descriptions    │  │
│  └───────────────────┬───────────────────────────┘  │
│                      │ delegate                     │
│  ┌───────────────────▼───────────────────────────┐  │
│  │              agents/*.py                      │  │
│  │   15 agent classes (ArangoAgentBase)           │  │
│  │   Business logic + error handling             │  │
│  └───────────────────┬───────────────────────────┘  │
│                      │ python-arango               │
│  ┌───────────────────▼───────────────────────────┐  │
│  │          arango_connector.py                  │  │
│  │   Connection pool, auth, SSL, lifespan        │  │
│  └───────────────────┬───────────────────────────┘  │
└──────────────────────┼──────────────────────────────┘
                       │ HTTP(S)
┌──────────────────────▼──────────────────────────────┐
│              ArangoDB Server                        │
│      (Single / Cluster / Enterprise)                │
└─────────────────────────────────────────────────────┘
```

### 4.2 Layer Responsibilities

| Layer | Files | Responsibility |
|-------|-------|----------------|
| **Entry point** | `main.py` | CLI bootstrap, logging, event loop policy, `mcp_app.run(transport="stdio")` |
| **Server** | `server.py` | FastMCP instance, LLM-facing instructions, tool registration via side-effect imports |
| **Configuration** | `config.py` | `pydantic-settings` with `ARANGO_*` env prefix, SSL validation, `.env` support |
| **Connector** | `arango_connector.py` | `ArangoDBConnector` singleton, `connect`/`disconnect`, `get_db`/`get_system_db`, health check, async lifespan |
| **Tools** | `mcp_tools/*.py` | Thin `@mcp_app.tool` wrappers with Pydantic `Field` descriptions; delegate to agents |
| **Agents** | `agents/*.py` | Business logic classes; each inherits `ArangoAgentBase`, implements `async arun()` |
| **Utilities** | `aql_utils.py` | AQL identifier validation (`validate_aql_identifier`, `validate_aql_identifiers`) |
| **Manuals** | `manuals/*.md` | AQL reference, optimization guide, Cypher→AQL migration |

### 4.3 Key Design Patterns

| Pattern | Application |
|---------|-------------|
| **Agent-per-domain** | Each functional area has a dedicated agent class for testability and separation of concerns |
| **Decorator-based error handling** | `handle_arango_errors` in `agent_base.py` eliminates try/except boilerplate across 5 agents |
| **Bind variable injection** | All user-provided values use AQL bind variables (`@param`); identifiers validated by `aql_utils` |
| **Lifespan management** | `arango_db_lifespan` async context manager ensures clean connect/disconnect tied to server lifecycle |
| **Configuration-as-code** | `pydantic-settings` with env vars, `.env` file, and runtime validation |

---

## 5. Configuration

### 5.1 Environment Variables

| Variable | Required | Default | Env Prefix | Description |
|----------|----------|---------|------------|-------------|
| `ARANGO_HOSTS` | Yes | — | `ARANGO_` | Comma-separated server URLs |
| `ARANGO_ROOT_USERNAME` | Yes | — | `ARANGO_` | Database username |
| `ARANGO_ROOT_PASSWORD` | Yes | — | `ARANGO_` | Database password |
| `ARANGO_DEFAULT_DB_NAME` | No | `_system` | `ARANGO_` | Default database for all operations |
| `ARANGO_MAX_CONNECTIONS` | No | `50` | `ARANGO_` | Connection pool size (reserved) |
| `ARANGO_TIMEOUT` | No | `30` | `ARANGO_` | Connection timeout in seconds (reserved) |
| `ARANGO_VERIFY_SSL` | No | `true` | `ARANGO_` | Enable SSL certificate verification |
| `ARANGO_SSL_CERT_PATH` | No | `""` | `ARANGO_` | Path to SSL certificate file |
| `LOG_LEVEL` | No | `INFO` | — | Server log level |
| `ENABLE_JS_TRANSACTIONS` | No | `false` | — | Enable server-side JavaScript transactions (security-sensitive) |
| `SERVER_NAME` | No | `ArangoDB MCP Server` | — | MCP server display name |
| `SERVER_VERSION` | No | `2.0.0` | — | MCP server version string |

### 5.2 MCP Client Configuration

Tools are exposed over **stdio transport**. Clients configure the server in their MCP JSON:

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
        "ARANGO_ROOT_PASSWORD": "your_password",
        "ARANGO_DEFAULT_DB_NAME": "myapp"
      }
    }
  }
}
```

---

## 6. Testing

### 6.1 Test Infrastructure

| Component | Description |
|-----------|-------------|
| **Framework** | pytest with `pytest-asyncio` (auto mode), `pytest-timeout` (120s) |
| **Database provisioning** | `conftest.py` auto-launches a Docker ArangoDB container on a random port per session; tears down after tests |
| **External instance** | Set `ARANGO_HOSTS` to skip Docker and test against an existing ArangoDB |
| **Connector patching** | `patch_connector` fixture monkeypatches the global `arango_connector` to use ephemeral test databases |
| **Vector detection** | `vector_index_supported` fixture probes the server to conditionally skip vector tests |

### 6.2 Test Coverage

| Test File | Agents / Areas Covered |
|-----------|------------------------|
| `test_connectivity.py` | Raw driver smoke tests (version, collections, docs, AQL, indexes) |
| `test_agents.py` | CollectionManagement, DocumentCRUD, IndexManagement, AQLExecution, ClusterManagement, GraphManagement |
| `test_aql_utils.py` | AQL identifier validation functions (53 test cases incl. injection vectors) |
| `test_database_manual_analyzer.py` | DatabaseManagementAgent, ManualManagementAgent, AnalyzerManagementAgent |
| `test_vector_search.py` | VectorSearchAgent, ViewManagementAgent, IndexManagement (vector paths) |
| `test_traversal.py` | GraphTraversalAgent, AQL explain/validate |
| `test_transactions.py` | TransactionManagementAgent, BackupManagementAgent |
| `test_users.py` | UserManagementAgent (users + permissions) |
| `test_cluster.py` | Cluster-specific tests (manual; excluded from CI) |

### 6.3 CI/CD

| Component | Configuration |
|-----------|---------------|
| **Platform** | GitHub Actions (`ci.yml`) |
| **Triggers** | Push/PR to `main` |
| **Lint job** | Ruff check + Ruff format check + Mypy type check |
| **Test job** | pytest with coverage across Python 3.10 and 3.11, ArangoDB 3.12 Docker |
| **Coverage** | `pytest-cov` reports on `agents/`, `mcp_tools/`, `aql_utils.py` |
| **Exclusions** | `test_cluster.py` excluded (requires multi-server deployment) |

---

## 7. Dependencies

### 7.1 Runtime

| Package | Version | Purpose |
|---------|---------|---------|
| `python` | ^3.10 | Language runtime |
| `python-arango` | ^8.1 | ArangoDB Python driver |
| `mcp` | ^1.0 | Model Context Protocol SDK |
| `fastmcp` | ^0.2 | FastMCP server framework |
| `pydantic` | ^2.0 | Data validation and serialization |
| `pydantic-settings` | ^2.0 | Environment-based configuration |
| `anyio` | ^4.5 | Async I/O compatibility |

### 7.2 Development

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | ^8.0 | Test framework |
| `pytest-asyncio` | ^0.24 | Async test support |
| `pytest-timeout` | ^2.2 | Test timeout enforcement |
| `black` | ^24.0 | Code formatter |
| `isort` | ^5.13 | Import sorter |
| `mypy` | ^1.0 | Static type checker |
| `ruff` | ^0.8 | Fast linter and formatter |
| `pytest-cov` | ^5.0 | Test coverage reporting |

---

## 8. Development Lifecycle

### 8.1 Release History

| Phase | Commit Range | Features Added |
|-------|-------------|----------------|
| Initial | `c4cc373` | Core MCP server, document CRUD, AQL execution, collection management |
| Manuals | `d4fe0bf` | AQL reference manuals, `get-aql-manual` tool |
| Optimization | `2af8c5f` | AQL optimization guide |
| Refactor | `e440d48` | Architecture refactor for cursor connection handling |
| Phase 1 | `4cce34e` | Docker test infra, bug fixes, expanded CRUD, python-arango 8.x |
| Phase 2 | `81d189a` | Sharding params on `create-collection`, complete document CRUD |
| Phase 3 | `a9e84a0` | Cluster management agent/tools, SmartGraph support |
| Phase 4 | `c9157b5` | Vector search (ANN), hybrid search, search-alias views |
| Phase 5 | `5cc5e87` | Graph traversals, AQL explain/validate, server instructions |
| Phase 6 | `a4e0bc1` | Stream transactions and hot backup tools |
| Phase 8 | `03e2fae` | Comprehensive README, lint cleanup |
| CI | `fcd3a0e`–`66b603e` | GitHub Actions CI workflow |
| Users | `f311408` | User and permission management (9 tools, 74 total) |
| Hardening | `5e941b2` | Security fixes, code quality, test expansion, tooling |

### 8.2 Adding New Tools

1. Create an agent in `agents/` inheriting from `ArangoAgentBase`
2. Optionally apply `@handle_arango_errors` decorator for standard error handling
3. Create tool definitions in `mcp_tools/` using `@mcp_app.tool` with Pydantic `Field` descriptions
4. Import the new tool module in both `mcp_tools/__init__.py` and `server.py`
5. Add tests in `tests/`
6. Update the tool count in `server.py` instructions and `README.md`

---

## 9. Known Limitations & Future Work

### 9.1 Current Limitations

| Area | Limitation |
|------|-----------|
| **Transport** | stdio only; no HTTP/SSE mode |
| **Authentication** | Server-level credentials only; no per-tool auth or multi-tenant support |
| **Connection pooling** | `max_connections` and `timeout` config fields are defined but not yet wired to the driver |
| **Metrics** | `enable_metrics` field reserved but no metrics collection implemented |
| **Cluster CI** | Cluster-specific tests excluded from CI (require multi-server deployment) |

### 9.2 Planned Features (per branch history)

| Feature | Branch | Status |
|---------|--------|--------|
| User & permission management | `feature/user-permission-management` | **Merged** to `main` |
| HTTP transport mode | `feature/http-mode` | In progress |
| Performance profiling | `feature/profiling` | In progress |
| SSL implementation enhancements | `Implemented_SSL` | In progress |
| Query optimization tools | `MCP_Server_Optimization_Query` | In progress |

---

## 10. Glossary

| Term | Definition |
|------|-----------|
| **MCP** | Model Context Protocol — an open standard for connecting AI assistants to external tools and data sources |
| **AQL** | ArangoDB Query Language — SQL-like language for querying documents, graphs, and search |
| **ANN** | Approximate Nearest Neighbor — vector similarity search algorithm |
| **SmartGraph** | ArangoDB Enterprise feature for co-locating graph vertices and edges by a shard key for optimal traversal performance |
| **SatelliteGraph** | ArangoDB Enterprise feature where graph data is replicated to all DB servers for local traversal |
| **Stream Transaction** | Multi-document ACID transaction in ArangoDB that spans multiple requests |
| **BM25** | Best Matching 25 — probabilistic text relevance scoring function used in ArangoSearch |
| **MDI Index** | Multi-Dimensional Index — for efficient multi-attribute range queries |
