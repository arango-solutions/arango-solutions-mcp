# Product Requirements Document — ArangoDB MCP Server

**PRD Version:** 3.0
**Current Product Version:** 2.0.0
**Last Updated:** August 6, 2026
**Status:** Requirement-level tracking; approved v3 requirements are not implementation claims
**Repository:** [arango-solutions/arango-solutions-mcp](https://github.com/arango-solutions/arango-solutions-mcp)

---

## 1. Overview

### 1.1 Product Summary

The ArangoDB MCP Server is a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that catalogs **81 tools** giving AI assistants (Cursor, Claude Desktop, and any MCP-compatible client) comprehensive, programmatic access to ArangoDB's multi-model database capabilities. Version 3 exposes a compact 17-tool readonly profile by default; broader write, operator, admin, graph, and search surfaces require explicit startup policy. It bridges the gap between natural-language AI interactions and ArangoDB's document, graph, search, and cluster features — enabling AI agents to build, query, manage, and administer ArangoDB deployments without hand-written driver code.

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
3. **Safety by default** — Destructive operations require explicit parameters; AQL identifier injection is prevented by validation; sensitive data is redacted from logs. The HTTP / SSE transport refuses to bind to a non-loopback interface unless `MCP_AUTH_TOKEN` is set, so the server cannot be exposed publicly without authentication.
4. **AI-optimized ergonomics** — Tool descriptions, server instructions, and error messages are written for LLM consumption, not human CLI users.
5. **Testable domain logic** — Core MCP tool definitions are thin Pydantic-validated wrappers around agent classes. Explicit tool-layer exceptions (currently embedding and pattern-memory tools) MUST use the shared async/error contract, remain independently testable, and be tracked as an architecture exception until extracted or accepted.

### 1.5 Contract Status and Version Policy

Every requirement has a stable ID and one state:

| State | Meaning |
|-------|---------|
| **CURRENT** | Implemented in product code or documentation and backed by the cited verification path |
| **PARTIAL** | Some implementation exists, but the acceptance gate is not yet satisfied |
| **APPROVED** | Accepted product requirement; implementation and tests are still required |
| **NON-GOAL** | Explicitly excluded from the current product contract |

The current 2.x behavior remains available during migration. Version 3 is a deliberate breaking
contract: `readonly` becomes the default access profile, the result envelope is versioned, and
legacy full-access/shared-token modes are temporary compatibility options with explicit
deprecation warnings. No scorecard or release may claim a requirement is CURRENT without the
required evidence class.

---

## 2. Current Functional Baseline

The tool rows in this section describe the current 81-tool surface. Registration and schema
inventory are mechanically checked by `tests/test_mcp_e2e.py`; future product requirements and
their implementation states are tracked separately in §3.8.

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

**Implementation:** `src/arangodb_mcp/agents/document_crud_agent.py` → `src/arangodb_mcp/mcp_tools/document_tools.py`

### 2.2 Collection Management (4 tools)

Create and manage document and edge collections with full cluster-aware configuration.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| C-1 | `list-collections` | List all user-defined collections in a database | `database_name` |
| C-2 | `create-collection` | Create document or edge collections | `collection_name`, `collection_type`, `number_of_shards`, `shard_keys`, `replication_factor`, `write_concern`, `sharding_strategy`, `computed_values` |
| C-3 | `delete-collection` | Drop a collection | `collection_name` |
| C-4 | `get-collection-properties` | Retrieve stats, shard config, revision, document count | `collection_name` |

**Implementation:** `src/arangodb_mcp/agents/collection_management_agent.py` → `src/arangodb_mcp/mcp_tools/collection_tools.py`

### 2.3 Database Management (4 tools)

Manage ArangoDB databases (requires `_system` database access).

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| DB-1 | `list-databases` | List all databases on the server | — |
| DB-2 | `create-database` | Create a new database | `database_name` |
| DB-3 | `delete-database` | Drop a database (blocks `_system` deletion) | `database_name` |
| DB-4 | `get-database-info` | Retrieve database properties | `database_name` |

**Implementation:** `src/arangodb_mcp/agents/database_management_agent.py` → `src/arangodb_mcp/mcp_tools/database_tools.py`

### 2.4 Graph Management (5 tools)

Manage named graphs including Enterprise features (SmartGraph, SatelliteGraph, EnterpriseGraph).

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| G-1 | `list-graphs` | List all named graphs | `database_name` |
| G-2 | `create-graph` | Create a named graph with edge definitions | `graph_name`, `edge_definitions`, `orphan_collections`, `smart`, `smart_field`, `shard_count`, `replication_factor`, `is_satellite` |
| G-3 | `delete-graph` | Drop a graph (optionally its collections) | `graph_name`, `drop_collections` |
| G-4 | `create-edge` | Insert an edge between vertices within a graph | `graph_name`, `edge_collection_name`, `from_vertex_id`, `to_vertex_id`, `edge_data` |
| G-5 | `get-graph-properties` | Retrieve graph configuration and edge definitions | `graph_name` |

**Implementation:** `src/arangodb_mcp/agents/graph_management_agent.py` → `src/arangodb_mcp/mcp_tools/graph_tools.py`

### 2.5 Graph Traversals (4 tools)

AQL-backed traversal queries with automatic query generation.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| T-1 | `graph-traverse` | Multi-depth traversal with filtering | `start_vertex`, `direction`, `min_depth`, `max_depth`, `graph_name` or `edge_collections`, `vertex_filters`, `edge_filters`, `return_vertices`, `return_edges`, `return_paths` |
| T-2 | `graph-shortest-path` | Single shortest path (optionally weighted) | `start_vertex`, `target_vertex`, `graph_name`, `weight_attribute` |
| T-3 | `graph-k-shortest-paths` | K alternative shortest paths | `start_vertex`, `target_vertex`, `limit` |
| T-4 | `graph-neighbors` | Deduplicated neighbor discovery at a given depth | `start_vertex`, `depth`, `deduplicate` |

**Implementation:** `src/arangodb_mcp/agents/graph_traversal_agent.py` → `src/arangodb_mcp/mcp_tools/traversal_tools.py`

### 2.6 AQL Query Engine (3 tools)

Direct AQL execution with plan analysis and syntax validation.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| Q-1 | `execute-aql-query` | Execute AQL with bind variables; returns results, stats, and counts | `aql_query`, `bind_vars`, `database_name` |
| Q-2 | `explain-aql-query` | Execution plan analysis (indexes, costs, optimizer rules) | `aql_query`, `bind_vars`, `all_plans`, `max_plans`, `opt_rules` |
| Q-3 | `validate-aql-query` | Syntax check without execution | `aql_query` |

**Implementation:** `src/arangodb_mcp/agents/aql_execution_agent.py` → `src/arangodb_mcp/mcp_tools/aql_tools.py`

### 2.7 Index Management (3 tools)

Create and manage all ArangoDB index types including vector and MDI.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| I-1 | `list-indexes` | List all indexes on a collection | `collection_name` |
| I-2 | `create-index` | Create any index type | `collection_name`, `index_definition` (type, fields, params) |
| I-3 | `delete-index` | Remove an index (blocks primary index deletion) | `collection_name`, `index_id_or_name` |

**Supported index types:** `persistent`, `inverted`, `geo`, `ttl`, `fulltext`, `mdi`, `mdi-prefixed`, `vector`

**Implementation:** `src/arangodb_mcp/agents/index_management_agent.py` → `src/arangodb_mcp/mcp_tools/index_tools.py`

### 2.8 Vector & Semantic Search (2 tools)

Approximate nearest-neighbor and hybrid search. Requires ArangoDB 3.12.4+ with `--experimental-vector-index`.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| V-1 | `vector-search` | ANN search using `APPROX_NEAR_*` functions | `collection_name`, `vector_field`, `query_vector`, `metric` (cosine/l2/innerProduct), `limit`, `n_probe`, `return_fields`, `filters` |
| V-2 | `hybrid-search` | Combined vector similarity + BM25 text search with weighted fusion | `collection_name`, `vector_field`, `query_vector`, `view_name`, `text_field`, `text_query`, `text_analyzer`, `vector_weight`, `text_weight` |

**Implementation:** `src/arangodb_mcp/agents/vector_search_agent.py` → `src/arangodb_mcp/mcp_tools/vector_tools.py`

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

**Implementation:** `src/arangodb_mcp/agents/view_management_agent.py` → `src/arangodb_mcp/mcp_tools/view_tools.py`

### 2.10 Analyzers (4 tools)

Manage text analyzers for ArangoSearch.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| A-1 | `list-analyzers` | List all analyzers in a database | `database_name` |
| A-2 | `create-analyzer` | Create a custom analyzer | `analyzer_name`, `analyzer_type`, `properties`, `features` |
| A-3 | `delete-analyzer` | Remove an analyzer | `analyzer_name` |
| A-4 | `get-analyzer-properties` | Retrieve analyzer definition | `analyzer_name` |

**Implementation:** `src/arangodb_mcp/agents/analyzer_management_agent.py` → `src/arangodb_mcp/mcp_tools/analyzer_tools.py`

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

**Implementation:** `src/arangodb_mcp/agents/cluster_management_agent.py` → `src/arangodb_mcp/mcp_tools/cluster_tools.py`

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

**Implementation:** `src/arangodb_mcp/agents/transaction_management_agent.py` → `src/arangodb_mcp/mcp_tools/transaction_tools.py`

### 2.13 Hot Backup — Enterprise Edition (4 tools)

Point-in-time deployment snapshots. Requires ArangoDB Enterprise.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| BK-1 | `create-backup` | Create a hot backup | `label`, `allow_inconsistent`, `force`, `timeout` |
| BK-2 | `list-backups` | List available backups | `backup_id` (optional filter) |
| BK-3 | `restore-backup` | Restore from a backup | `backup_id` |
| BK-4 | `delete-backup` | Permanently remove a backup | `backup_id` |

**Implementation:** `src/arangodb_mcp/agents/backup_management_agent.py` → `src/arangodb_mcp/mcp_tools/backup_tools.py`

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

**Implementation:** `src/arangodb_mcp/agents/user_management_agent.py` → `src/arangodb_mcp/mcp_tools/user_tools.py`

### 2.15 AQL Reference (1 tool)

Serve built-in AQL documentation to the AI assistant.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| M-1 | `get-aql-manual` | Retrieve AQL syntax, optimization, or Cypher→AQL migration guides | `manual_name` (`aql_ref`, `optimization`, `cypher2aql`) |

**Implementation:** `src/arangodb_mcp/agents/manual_management_agent.py` → `src/arangodb_mcp/mcp_tools/manual_tools.py`

### 2.16 Embeddings (2 tools)

Generate vector embeddings via the OpenAI embeddings REST API, powering vector/hybrid pattern search. Optional subsystem: when `OPENAI_API_KEY` is unset these tools return a clear error and the pattern tools degrade to keyword-only search, leaving the core 74-tool server unaffected.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| E-1 | `embed-text` | Generate embedding vectors for one or more text strings (programmatic callers) | `texts`, `model` |
| E-2 | `embed-document` | Embed a document's fields and store the vector on the document server-side (keeps large vectors out of the agent context) | `collection_name`, `document_key`, `source_fields`, `target_field` |

**Implementation:** `src/arangodb_mcp/mcp_tools/embedding_tools.py` (tool layer; shared helpers in `src/arangodb_mcp/mcp_tools/_support.py`)

### 2.17 Shared-Memory Patterns & Drift (5 tools)

Cross-project "dark factory" memory (see `CLAUDE.md`): reusable solution patterns and PRD-drift alerts stored in ArangoDB, retrieved by hybrid semantic search and linked into a provenance graph. Requires `OPENAI_API_KEY` for vector search; falls back to BM25 when absent.

| ID | Tool | Description | Key Parameters |
|----|------|-------------|----------------|
| P-1 | `pattern-search` | Hybrid vector + BM25 search over `shared_patterns` (RRF fusion, 1-hop graph expansion, graded re-rank by importance/recency/usage) | `query_text`, `limit`, `graph_expand`, `project_id` |
| P-2 | `save-pattern` | Embed-then-insert a solved-problem pattern; maintains `pattern_from_project` provenance and `pattern_relates_to` edges. Implicit `pattern_supersedes` edges are created for near-duplicates by default, but `force=true` records the candidate as genuinely distinct and skips implicit superseding; `supersedes_key` still performs explicit replacement and bi-temporal invalidation. | `problem_description`, `solution_summary`, `problem_category`, `project_id`, `importance`, `force`, `supersedes_key` |
| P-3 | `pattern-index` | Backfill the embedding and graph edges for one just-saved pattern | `document_key`, `rel_sim`, `sup_sim`, `top_k` |
| P-4 | `pattern-applied` | Record that surfaced patterns were reused, with an `outcome` (`worked`/`failed`): a `worked` apply bumps `usage_count`/`last_used`; a `failed` apply records negative signal (`applied_failed`) that down-weights the pattern via a success-rate factor in ranking — so a tried-but-unhelpful pattern is penalised, not rewarded | `keys`, `outcome` |
| P-5 | `save-drift-alert` | Upsert a PRD drift alert and link it to its project via an `alert_from_project` edge | `project_id`, `req_id`, `classification`, `status`, `evidence` |

**Implementation:** `src/arangodb_mcp/mcp_tools/pattern_memory_tools.py` (tool layer; shared helpers in `src/arangodb_mcp/mcp_tools/_support.py`). Unlike the 74 core tools, these carry business logic in the tool module rather than a dedicated agent (a known divergence from Design Principle 5, tracked as drift REQ-021); they honor the same async-safety and error contract as the agent tools via `src/arangodb_mcp/mcp_tools/_support.py` (`run_sync` off-loop dispatch + `arango_error_result` standardized envelope).

---

## 3. Non-Functional Requirements

### 3.1 Security

| Requirement | Implementation |
|-------------|----------------|
| **No hardcoded credentials** | All connection parameters via `ARANGO_*` environment variables; validated by Pydantic settings |
| **AQL injection prevention** | `src/arangodb_mcp/aql_utils.py` validates all identifiers before AQL interpolation; values use bind variables (`@param`) |
| **Log redaction** | Bind variable values are never logged; only parameter keys appear in log output. User-supplied AQL is also redacted by default (`<redacted len=N sha1=…>`) because inline literals can contain secrets. Set `LOG_AQL_QUERIES=true` to log the first 100 chars of the query for debugging. |
| **SSL/TLS by default** | `ARANGO_VERIFY_SSL` defaults to `true`; optional `ARANGO_SSL_CERT_PATH` with cross-platform path validation |
| **JS transaction gating** | `execute-transaction` disabled by default; requires `ENABLE_JS_TRANSACTIONS=true` to allow arbitrary JS execution on the server |
| **Defense-in-depth** | `_system` database deletion blocked at agent level (in addition to tool level) |
| **HTTP transport authentication** | HTTP supports a time-bounded constant-time shared-bearer compatibility mode and provider-neutral OIDC resource-server mode. OIDC performs discovery/JWKS rotation, asymmetric signature, issuer, audience, expiry/not-before, identity, scope, and database-claim validation and publishes RFC 9728 metadata. Non-loopback HTTP refuses to start without one complete auth mode. |
| **Query budget** | `DEFAULT_AQL_MAX_RUNTIME` defaults to 30 seconds and is clamped to the non-disableable production ceiling. Per-call overrides cannot disable or exceed that ceiling; the dispatch boundary also enforces catalog runtime, row, response-byte, bulk-input, and concurrency maxima. |
| **In-process secret protection** | Database, bearer, confirmation, OIDC credential-map, and OTLP header secrets use `pydantic.SecretStr` or redacted dataclasses. OIDC access-token claims never supply database passwords; server-side actor mappings resolve request-scoped credentials. Password-bearing tool parameters use `SecretStr` and audit events allow-list identifiers instead of serializing payloads. |

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
| **Cursor consumption** | All cursors fully iterated and results collected; no abandoned iterators |
| **Bind variables** | All AQL values passed as bind variables for server-side optimization |
| **Async safety** | Every blocking python-arango call is wrapped in `asyncio.to_thread()` via `ArangoAgentBase.run_sync()` so a single in-flight tool call cannot block the event loop, and concurrent tool calls run in parallel rather than serializing on the driver. |
| **Connection pooling** | Delegated to the python-arango driver's default `requests.Session`. Tunable pool sizing is tracked as future work. |
| **Load control** | Per-actor token-bucket rate limits and global, catalog-class, and per-tool concurrency ceilings are enforced atomically and return machine-readable retry metadata. |

### 3.4 Compatibility

| Requirement | Implementation |
|-------------|----------------|
| **ArangoDB versions** | 3.12+ (vector search requires 3.12.4+ with `--experimental-vector-index`); forward-compatible with 4.0 |
| **Python versions** | 3.10+ (uses `pyproject.toml` with `python = "^3.10"`) |
| **Platforms** | macOS, Linux, Windows — platform-specific event loop policies configured in `src/arangodb_mcp/main.py` |
| **MCP clients** | Any MCP-compatible client (Cursor IDE, Claude Desktop, Antigravity, custom integrations) |
| **Transport** | stdio (default for client-launched), SSE, and streamable-http (for standalone/Docker deployment) |
| **Deployment** | Client subprocess (stdio), standalone service (Docker), or bare-metal (any HTTP-capable host) |

### 3.5 Observability

| Requirement | Implementation |
|-------------|----------------|
| **Structured logging** | All agents use `logging.getLogger(__name__)`; log level configurable via `LOG_LEVEL` env var |
| **Startup diagnostics** | Server logs platform, Python version, server version, default database on startup |
| **Error context** | Error responses include `error` message, optional `error_code`, and agent-specific context |
| **Correlation** | HTTP and stdio dispatch establish request and trace IDs; W3C `traceparent`, `X-Request-ID`, worker-thread ArangoDB calls, embedding HTTP, logs, spans, and audit records share the same correlation context. |
| **Metrics** | `/metrics` exposes bounded-cardinality Prometheus tool, duration, error, AQL, dependency-pressure, and limiter series. Actor, database, query, document, and raw error values are never metric labels. |
| **Tracing** | OpenTelemetry spans use the pinned `src/arangodb_mcp/observability/conventions.py` mapping for `mcp.request`, `mcp.tool.call`, `arango.database`, and `dependency.embedding`; optional OTLP/HTTP export is configuration-driven. |
| **Audit** | The catalog dispatch boundary emits exactly one allow-listed, redacted structured audit event for every write/admin action attempt with actor, action, target identifiers, outcome, request ID, and trace ID. |

### 3.6 Provenance & Attribution

| Requirement | Implementation |
|-------------|----------------|
| **Write attribution** | Every write to shared memory (patterns, drift alerts, search-log rows, apply events) is stamped with the connected ArangoDB user — `saved_by`, `detected_by`/`closed_by`, `last_applied_by`, and `by` on search-log rows — via `_current_user()` (`src/arangodb_mcp/mcp_tools/pattern_memory_tools.py`). Deployments use per-developer scoped users, so the connection identity is the person. |
| **Apply trail** | `pattern-applied` maintains a capped (last-20) `apply_log` of `{by, at, outcome}` entries per pattern for a rolling reuse history. |
| **Non-blocking** | Attribution is best-effort and MUST never block or fail the underlying write. |

### 3.7 Retrieval Quality

| Requirement | Implementation |
|-------------|----------------|
| **Relevance-dominant ranking** | `pattern-search` fuses ANN vector + BM25 via Reciprocal Rank Fusion (k=10), then applies multiplicative salience — `score = relevance × (1 + 0.15·importance + 0.10·recency + 0.05·usage) × (0.6 + 0.4·success_rate)` — so importance, recency, usage and apply success-rate modulate ranking but can never substitute for semantic relevance. |
| **Measurable quality** | Versioned in-repository golden data and blocking baselines measure MRR@10, recall@5, and p50/p95/p99 retrieval latency before merge (`evals/data/retrieval_golden.v1.json`, `evals/baselines/quality.v1.json`, `evals/run_quality_gates.py`). |

### 3.8 Approved v3 Requirements and Traceability

Evidence classes are **STATIC** (source/configuration inspection), **TEST** (deterministic automated
test), **LIVE** (runtime integration, interoperability, load, or telemetry evidence), and
**EXTERNAL** (published artifact or independently observable adoption/governance evidence).
Acceptance requires every listed evidence class; a test is never a substitute for missing product
implementation.

#### Documentation and contract integrity

| ID | State | Owner | Requirement and acceptance gate | Required evidence |
|----|-------|-------|---------------------------------|-------------------|
| DOC-001 | CURRENT | Product | Tool-count claims MUST equal the registered MCP inventory; the current count is 81. | STATIC: `src/arangodb_mcp/server.py:18-66`; TEST: `tests/test_mcp_e2e.py:59-63` |
| DOC-002 | CURRENT | Quality | Test-count and test-tier claims MUST be generated or mechanically verified against the repository. | TEST: `scripts/verify_docs.py:33-42`, `tests/test_doc_consistency.py:21-37` |
| DOC-003 | CURRENT | Product | The PRD MUST use requirement-level states rather than a blanket implementation claim. | STATIC: `PRD.md:38-55`, `PRD.md:370-457` |
| DOC-004 | CURRENT | Architecture | Tool-layer business-logic exceptions MUST be explicit and retain async/error/test parity. | STATIC: `src/arangodb_mcp/mcp_tools/_support.py:33-59`; TEST: `tests/test_embedding_tools.py:44-60`, `tests/test_pattern_memory_tools.py:94-112` |
| DOC-005 | CURRENT | Release | Release-history entries MUST reference immutable commits or releases and MUST NOT say “uncommitted.” | STATIC: `PRD.md:713-732`; TEST: `scripts/verify_docs.py:108-109` |
| DOC-006 | CURRENT | Platform | The documented Compose quick start MUST require secret injection and start successfully without disabling the non-loopback auth guard. | STATIC: `docker-compose.yml:4-20`, `README.md:142-164`; TEST: `tests/test_deployment_contract.py:12-38`; LIVE: clean Compose smoke reached healthy MCP |
| DOC-007 | CURRENT | Platform | Vector capability claims MUST match the default Compose configuration or clearly document degraded mode. | STATIC: `docker-compose.yml:22-39`; TEST: `tests/test_deployment_contract.py:12-21`; LIVE: Compose vector-index probe passed |
| DOC-008 | CURRENT | Architecture | Every tool MUST return one versioned success/error envelope, with a time-bounded legacy adapter. | STATIC: `src/arangodb_mcp/contracts/v3_result.py:8-100`, `src/arangodb_mcp/policy/tool_manager.py:91-113`; TEST: `tests/test_v3_contract.py:25-101` covers every registered tool, error normalization, schema preservation, and adapter expiry; LIVE: 2026-08-06 authenticated Compose call returned root `contractVersion: "3.0"` and `status: "success"` |
| DOC-009 | CURRENT | Operations | `LOG_FORMAT`, redaction behavior, and supported structured fields MUST be documented from configuration. | STATIC: `README.md:103-128`, `PRD.md:526-550`; TEST: `scripts/verify_docs.py:45-51`, `scripts/verify_docs.py:100-106` |
| DOC-010 | CURRENT | Operations | `/healthz`, readiness semantics, authentication behavior, and container health checks MUST be documented and executable. | STATIC: `src/arangodb_mcp/asgi/health.py:13-93`, `Dockerfile:38-39`, `README.md:155-178`, `docs/slo.md:7-62`; TEST: `tests/test_health_endpoint.py:89-164`, `tests/test_app_factory.py:65-129`; LIVE: authenticated Compose smoke on 2026-08-05 returned `/livez` 200, `/readyz` 200/503 with dependency state, and deprecated `/healthz` alias metadata |
| DOC-011 | CURRENT | Quality | Documented environment variables, defaults, and conditional requirements MUST match `Settings`. | TEST: `scripts/verify_docs.py:45-51`, `scripts/verify_docs.py:100-106` |
| DOC-012 | CURRENT | Quality | CI MUST fail when tool counts, test inventory, configuration, or release evidence drifts from documentation. | STATIC: `.github/workflows/ci.yml:43-44`; TEST: `tests/test_doc_consistency.py:21-37` |

#### Agent ergonomics

| ID | State | Owner | Requirement and acceptance gate | Required evidence |
|----|-------|-------|---------------------------------|-------------------|
| AE-001 | CURRENT | Architecture | A canonical catalog MUST classify every tool by category, risk tier, read/write/admin class, scope, and confirmation policy; unknown tools fail registration. | STATIC: `src/arangodb_mcp/catalog/tools.yaml:1-106`, `src/arangodb_mcp/catalog/loader.py:21-148`, `src/arangodb_mcp/policy/tool_manager.py:38-85`; TEST: `tests/test_tool_policy.py:106-113`, `tests/test_tool_policy.py:183-196` |
| AE-002 | CURRENT | Product | Startup profiles MUST include `readonly`, `developer`, `operator`, and `admin`, with additive graph/search toolsets. | STATIC: `src/arangodb_mcp/config.py:146-163`, `src/arangodb_mcp/policy/profiles.py:10-89`; TEST: exact inventories and readonly-bounded graph/search additions in `tests/test_tool_policy.py:115-142` |
| AE-003 | CURRENT | Product | The default profile MUST expose a compact, task-appropriate surface rather than all 81 schemas. | STATIC: `src/arangodb_mcp/config.py:146-149`, `src/arangodb_mcp/policy/profiles.py:31-89`; TEST: 17-tool exact inventory and ≤9,000 estimated-token ceiling in `tests/test_tool_policy.py:199-207`; LIVE: authenticated Compose `tools/list` on 2026-08-06 returned 17 tools at 8,293 estimated tokens |
| AE-004 | CURRENT | Architecture | Runtime, rows, bytes, bulk input, and concurrency MUST have server-enforced maxima with machine-readable truncation/denial metadata. | STATIC: `src/arangodb_mcp/policy/limits.py:36-160`, `src/arangodb_mcp/policy/tool_manager.py:129-253`; TEST: `tests/test_safety_policy.py:178-253`; LIVE: authenticated Compose AQL returned 1,000 of 1,500 rows plus `row_limit_truncated` metadata on 2026-08-06 |
| AE-005 | CURRENT | Product | Manuals, schema summaries, active profile, and status MUST be resources; safe AQL/graph/search workflows SHOULD be prompts. | STATIC: `src/arangodb_mcp/mcp_content.py:22-164`; TEST: `tests/test_mcp_content.py:26-103`; LIVE: MCP listed/read 3 resources, 1 manual template, and 3 prompts on 2026-08-06 |
| AE-006 | CURRENT | Architecture | All tools MUST use one v3 result contract; compatibility mode MUST preserve schema introspection and have a removal date. | STATIC: `src/arangodb_mcp/contracts/v3_result.py:8-100`, `src/arangodb_mcp/policy/tool_manager.py:66-113`; TEST: all 81 registered tools, root structured output, legacy expiry, and input schemas in `tests/test_v3_contract.py:25-101` |

#### Security and authorization

| ID | State | Owner | Requirement and acceptance gate | Required evidence |
|----|-------|-------|---------------------------------|-------------------|
| SEC-001 | CURRENT | Security | Version 3 MUST default to readonly; write/admin tools are absent or denied unless explicitly enabled. | STATIC: `src/arangodb_mcp/config.py:146-149`, `src/arangodb_mcp/policy/profiles.py:31-89`, `src/arangodb_mcp/policy/tool_manager.py:38-113`; TEST: full-catalog readonly conformance in `tests/test_tool_policy.py:106-142`; LIVE: 2026-08-06 Compose exposed 17 read tools and rejected direct `create-document` execution |
| SEC-002 | CURRENT | Security | AQL policy MUST classify parsed queries as read, mutation, or ambiguous; readonly mode rejects mutation and fails closed on ambiguity. Keyword regex alone is insufficient. | STATIC: authoritative parser AST classification in `src/arangodb_mcp/policy/aql_classifier.py:10-84`, integrated before execution at `src/arangodb_mcp/agents/aql_execution_agent.py:64-91`; TEST: `tests/test_safety_policy.py:69-175`; LIVE: parser classified `RETURN 1` read and `INSERT` mutation on 2026-08-06 |
| SEC-003 | CURRENT | Security | Production policy MUST enforce non-disableable maxima for query runtime, output, bulk input, and concurrent work. | STATIC: code ceilings/clamping in `src/arangodb_mcp/policy/limits.py:36-160` and dispatch enforcement in `src/arangodb_mcp/policy/tool_manager.py:129-253`; TEST: disable, timeout, bulk, byte, row, and concurrency bypasses in `tests/test_safety_policy.py:164-253`; LIVE: 1,500-row query truncated to 1,000 with metadata |
| SEC-004 | CURRENT | Security | Irreversible actions MUST require actor/action/parameter/expiry-bound human confirmation and MUST NOT be self-approved by an automated client. | STATIC: trusted CLI `scripts/mint_confirmation.py:1-57`, binding/expiry/one-use verification `src/arangodb_mcp/policy/confirmation.py:30-230`, pre-dispatch enforcement `src/arangodb_mcp/policy/tool_manager.py:63-253`; TEST: all irreversible entries refuse without approval plus actor/action/parameter/expiry/replay cases in `tests/test_safety_policy.py:256-337` and `tests/test_quality_gates.py:15-43`; LIVE: unapproved AQL mutation denied and exact out-of-band token allowed one mutation on 2026-08-06 |
| SEC-005 | CURRENT | Security | Deployments MUST support explicit tool/category denylists in addition to profiles. | STATIC: `src/arangodb_mcp/config.py:154-161`, `src/arangodb_mcp/policy/context.py:12-37`, `src/arangodb_mcp/policy/profiles.py:51-89`; TEST: typo fail-closed and denied tools absent/unexecutable in `tests/test_tool_policy.py:145-181` |
| SEC-006 | CURRENT | Identity | HTTP production mode MUST support OAuth 2.1/OIDC resource-server validation, RFC 9728 metadata, per-request identity, audience/expiry validation, and scopes. | STATIC: `src/arangodb_mcp/oidc.py:39-365`, `src/arangodb_mcp/asgi/app_factory.py:21-106`, `src/arangodb_mcp/config.py:202-254`; TEST: signature/issuer/audience/expiry/not-before, JWKS rotation, fail-closed discovery, metadata, and context reset in `tests/test_auth_middleware.py:363-548`, `tests/test_app_factory.py:193-221`; LIVE: containerized ephemeral-key reference IdP completed discovery/JWKS and an authenticated signed-JWT MCP call via `scripts/run_phase4_integration.py:159-296` on 2026-08-06 |
| SEC-007 | CURRENT | Identity | Effective authority MUST intersect token scopes, profile, database allowlist, tool policy, and least-privilege credential provider. | STATIC: request identity/credentials `src/arangodb_mcp/policy/actor_context.py:11-67`, trusted mapping `src/arangodb_mcp/policy/credentials.py:21-121`, runtime intersection `src/arangodb_mcp/policy/tool_manager.py:161-170,434-471`, request-scoped connector `src/arangodb_mcp/arango_connector.py:154-185`; TEST: scope/tool/database denial in `tests/test_tool_policy.py:229-302` and concurrent credential isolation in `tests/test_arango_connector.py:208-244`; LIVE: Phase 4 signed token was intersected with readonly profile, `_system` token/mapping allowlists, and server-side credentials before `list-databases` succeeded |

#### Deployment and protocol

| ID | State | Owner | Requirement and acceptance gate | Required evidence |
|----|-------|-------|---------------------------------|-------------------|
| DEP-001 | CURRENT | Protocol | The server MUST pass pinned MCP 2026-07-28 stateless interoperability, routing-header, cache-scope/TTL, Host, and Origin checks while retaining documented compatibility mode. | STATIC: `src/arangodb_mcp/server.py:88-106`, `src/arangodb_mcp/middleware/protocol.py:24-236`, `src/arangodb_mcp/middleware/transport_security.py:11-30`, `src/arangodb_mcp/protocol_compat.py:1-31`; TEST: `tests/test_protocol_interop.py:64-139`, `tests/test_protocol_metadata.py:77-174`, `tests/test_protocol_security.py:31-78`; LIVE: authenticated Compose probe on 2026-08-05 negotiated 2026-07-28 stateless initialize, listed 81 tools with cache metadata, called `list-databases`, rejected missing auth, and rejected hostile Origin |
| DEP-002 | CURRENT | Platform | Docker Compose MUST provide authenticated MCP startup, vector-capable ArangoDB, dependency-aware MCP health checks, and an executable quick start. | STATIC: `Dockerfile:20-28`, `docker-compose.yml:4-39`, `README.md:142-164`; TEST: `tests/test_deployment_contract.py:12-38`, `tests/test_health_endpoint.py:84-164`; LIVE: both containers healthy, `/healthz` 200, vector probe passed, unauthenticated MCP rejected |
| DEP-003 | PARTIAL | Release | The project MUST publish installable Python and immutable non-root container artifacts. | STATIC: package/entry point/data in `pyproject.toml:10-18`, wheel-installed immutable non-root image in `Dockerfile:12-29,46-51`; TEST: isolated wheel build/install/import/data/CLI verification in `scripts/verify_wheel.py:61-121` and local image contract in `tests/test_deployment_contract.py:65-82` pass; EXTERNAL gap: no PyPI wheel or GHCR digest has been published |
| DEP-004 | CURRENT | Platform | A supported Kubernetes/Helm deployment MUST define probes, resources, secrets, and upgrade guidance. | STATIC: supported chart and upgrade/rollback guidance in `deploy/helm/arangodb-mcp/README.md:1-113`; TEST: strict Helm lint/render plus kubeconform in `scripts/verify_helm.sh:13-54`; LIVE: `scripts/run_helm_kind_smoke.sh:47-180` completed local kind install, probes, authenticated MCP call, upgrade, and post-upgrade readiness |

#### Operations and observability

| ID | State | Owner | Requirement and acceptance gate | Required evidence |
|----|-------|-------|---------------------------------|-------------------|
| OPS-001 | CURRENT | Operations | Every request MUST receive a propagated request/trace ID across MCP, tool, ArangoDB, and embedding calls. | STATIC: `src/arangodb_mcp/middleware/request_context.py:27-76`, `src/arangodb_mcp/observability/context.py:1-98`, `src/arangodb_mcp/observability/dependencies.py:79-131`, `src/arangodb_mcp/mcp_tools/embedding_tools.py:69-108`; TEST: HTTP/worker/embedding propagation in `tests/test_app_factory.py:97-119`, `tests/test_safety_policy.py:395-425`, `tests/test_embedding_tools.py:110-154`; LIVE: Phase 4 collector received correlated request/tool/database spans |
| OPS-002 | CURRENT | Operations | Prometheus metrics MUST expose tool counts, latency, errors, AQL runtime, pool pressure, and dependency calls with bounded cardinality. | STATIC: fixed label sets and collectors in `src/arangodb_mcp/observability/metrics.py:15-163`, public scrape handler `src/arangodb_mcp/observability/http.py:10-34`; TEST: scrape and fixed-label contract in `tests/test_app_factory.py:97-119`; LIVE: pinned Prometheus `v3.2.1` scraped the MCP target and observed a successful `list-databases` metric via `docker-compose.phase4.yml:99-115` |
| OPS-003 | CURRENT | Operations | OpenTelemetry traces MUST cover request, tool, database, and embedding spans using a pinned internal-to-MCP convention mapping. | STATIC: `src/arangodb_mcp/observability/conventions.py:1-31`, `src/arangodb_mcp/observability/telemetry.py:22-75`, dispatch/dependency spans in `src/arangodb_mcp/policy/tool_manager.py:173-244`, `src/arangodb_mcp/observability/dependencies.py:79-131`; TEST: parent hierarchy and embedding propagation in `tests/test_safety_policy.py:395-425`, `tests/test_embedding_tools.py:110-154`; LIVE: pinned OTLP collector `0.123.0` received `mcp.request`, `mcp.tool.call`, and `arango.database` spans |
| OPS-004 | CURRENT | Security | Every mutation and privileged action MUST emit one structured redacted audit event with actor, action, target, outcome, and correlation ID. | STATIC: central audit boundary `src/arangodb_mcp/policy/tool_manager.py:173-244`, identifier allowlist `src/arangodb_mcp/observability/audit.py:14-60`; TEST + LIVE: every catalog write/admin attempt emitted exactly one event and password/token/AQL/payload sentinels were absent in `tests/test_safety_policy.py:428-464` |
| OPS-005 | CURRENT | Operations | Per-actor rate limits and global/tool-class concurrency limits MUST return retry metadata and export limiter metrics. | STATIC: atomic limiter `src/arangodb_mcp/policy/limits.py:176-350`, dispatch integration `src/arangodb_mcp/policy/tool_manager.py:279-367`, fixed metrics `src/arangodb_mcp/observability/metrics.py:76-145`; TEST: rate/retry, global, and class ceilings in `tests/test_safety_policy.py:263-391`; LIVE: configured Phase 4 process exported limiter series and the deterministic in-flight maximum never exceeded its configured ceiling |
| OPS-006 | CURRENT | Operations | Liveness and dependency-aware readiness MUST be distinct, containerized, documented, and tied to explicit SLOs. | STATIC: `src/arangodb_mcp/asgi/health.py:13-93`, `Dockerfile:38-39`, `docker-compose.yml:23-34`, `docs/slo.md:7-62`; TEST: `tests/test_health_endpoint.py:89-164`, `tests/test_deployment_contract.py:26-49`; LIVE: 2026-08-05 Compose failure-mode probe kept `/livez` at 200 while stopped ArangoDB caused `/readyz` 503, then recovered healthy after restart |

#### Reliability and verification

| ID | State | Owner | Requirement and acceptance gate | Required evidence |
|----|-------|-------|---------------------------------|-------------------|
| REL-001 | PARTIAL | Quality | Required CI MUST be green and enforce a measured non-regression coverage floor. | STATIC: `.github/workflows/ci.yml:37-112`, `pyproject.toml:94-96`; TEST: Ruff, Mypy, 480 tests, 82.64% measured coverage, and the 79% floor pass locally; EXTERNAL: protected required checks blocked on repository-admin action tracked by [issue #6](https://github.com/arango-solutions/arango-solutions-mcp/issues/6) |
| REL-002 | PARTIAL | Security | CI MUST run dependency audit, CodeQL, secret scanning, and container/dependency vulnerability checks with a documented severity policy. | STATIC: `.github/dependabot.yml:1-24`, `.github/workflows/security.yml:1-104`, `SECURITY.md:17-60`; TEST: `tests/test_security_contract.py:12-85`, exception-free pip-audit, and local built-image Trivy gate passed; EXTERNAL: first CI secret/image scan run on this implementation pending |
| REL-003 | CURRENT | Quality | A scheduled job MUST execute real multi-server cluster tests rather than deselecting them. | STATIC: `.github/workflows/cluster-nightly.yml:1-113`; TEST: `tests/test_cluster.py:1-225`, `tests/test_deployment_contract.py:54-63`; LIVE + EXTERNAL: [Nightly Cluster run 31068063574](https://github.com/arango-solutions/arango-solutions-mcp/actions/runs/31068063574) completed successfully on 2026-08-05 against the pinned three-machine deployment |
| REL-004 | PARTIAL | Protocol | CI MUST verify supported MCP transports and strict/legacy interoperability with pinned reference clients. | TEST: `tests/test_protocol_interop.py:64-139` covers strict/auto/legacy Streamable HTTP and `tests/test_app_factory.py:59-75` covers SSE/stdio composition; EXTERNAL: first CI run on this matrix pending |
| REL-005 | CURRENT | Quality | Deterministic task replays MUST gate tool selection and destructive refusal; live-model evaluations MAY run as advisory nightly checks. | STATIC: `evals/data/tool_selection.v1.json`, `evals/data/destructive_refusal.v1.json`, `evals/run_quality_gates.py:40-92`, `.github/workflows/ci.yml:43-50`; TEST + LIVE: deterministic gate produced selection 90% and destructive refusal 100% on 2026-08-06 |
| REL-006 | CURRENT | Quality | Retrieval quality and performance MUST have versioned in-repository baselines and blocking regression thresholds. | STATIC: `evals/data/retrieval_golden.v1.json`, `evals/baselines/quality.v1.json`, `evals/run_quality_gates.py:95-170`; TEST: `tests/test_quality_gates.py:15-43`; LIVE: v1 gate produced MRR@10 1.0, recall@5 1.0, p50 0.097ms, p95 0.323ms, p99 0.390ms on 2026-08-06 |

#### Release maturity and governance

| ID | State | Owner | Requirement and acceptance gate | Required evidence |
|----|-------|-------|---------------------------------|-------------------|
| MAT-001 | PARTIAL | Release | Releases MUST use trusted publishing, signed provenance, SBOMs, keyless image signatures, changelogs, and automated verification. | STATIC: trusted PyPI, provenance/SBOM attestations, keyless image signing, digest scanning/verification, and GitHub release creation in `.github/workflows/release.yml:113-347`, with `CHANGELOG.md:1-22`; TEST: workflow markers are enforced by `scripts/verify_docs.py:165-173`; EXTERNAL gap: no published wheel/image, signature, SBOM, or attestation exists to verify |
| MAT-002 | PARTIAL | Product | The repository MUST publish `SECURITY.md`, `CONTRIBUTING.md`, `CODEOWNERS`, threat model, support policy, and deprecation policy. | STATIC: local governance and response paths in `SECURITY.md:1-80`, `CONTRIBUTING.md:1-51`, `.github/CODEOWNERS:1-8`, `docs/threat-model.md:1-101`, `SUPPORT.md:1-29`, and `docs/deprecation-policy.md:1-35`; TEST: presence/link checks in `scripts/verify_docs.py:186-233`; EXTERNAL gap: these worktree files are not yet published in the public repository |
| MAT-003 | APPROVED | Product | An A claim requires an independent scorecard rerun at ≥90 after at least 30 days of green CI, telemetry, interoperability, release, and external-use evidence. | LIVE + EXTERNAL: dated evidence report and regrade |

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
│       Installable `arangodb_mcp` package              │
│         (src/arangodb_mcp/server.py)                  │
│  ┌───────────────────────────────────────────────┐  │
│  │       src/arangodb_mcp/mcp_tools/*.py         │  │
│  │   81 @mcp_app.tool functions (74 core +7 mem)  │  │
│  │   Pydantic Field validation + descriptions    │  │
│  └───────────────────┬───────────────────────────┘  │
│                      │ delegate                     │
│  ┌───────────────────▼───────────────────────────┐  │
│  │        src/arangodb_mcp/agents/*.py           │  │
│  │   15 agent classes (ArangoAgentBase)           │  │
│  │   Business logic + error handling             │  │
│  └───────────────────┬───────────────────────────┘  │
│                      │ python-arango               │
│  ┌───────────────────▼───────────────────────────┐  │
│  │    src/arangodb_mcp/arango_connector.py       │  │
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
| **Console entry point** | `src/arangodb_mcp/cli.py`, `src/arangodb_mcp/main.py` | Installed `arangodb-mcp` command, version reporting, logging, event loop policy, and transport bootstrap |
| **ASGI composition** | `src/arangodb_mcp/asgi/*.py` | HTTP transport composition, public liveness/readiness routing, and middleware ordering |
| **HTTP middleware** | `src/arangodb_mcp/middleware/*.py` | MCP request-metadata validation, Host/Origin enforcement, and request context |
| **Server** | `src/arangodb_mcp/server.py` | FastMCP instance, LLM-facing instructions, tool registration via side-effect imports |
| **Configuration** | `src/arangodb_mcp/config.py` | `pydantic-settings` with `ARANGO_*` env prefix, SSL validation, `.env` support |
| **Connector** | `src/arangodb_mcp/arango_connector.py` | `ArangoDBConnector` singleton, `connect`/`disconnect`, `get_db`/`get_system_db`, health check, async lifespan |
| **Tools** | `src/arangodb_mcp/mcp_tools/*.py` | Thin `@mcp_app.tool` wrappers with Pydantic `Field` descriptions; delegate to agents |
| **Agents** | `src/arangodb_mcp/agents/*.py` | Business logic classes; each inherits `ArangoAgentBase`, implements `async arun()` |
| **Utilities** | `src/arangodb_mcp/aql_utils.py` | AQL identifier validation (`validate_aql_identifier`, `validate_aql_identifiers`) |
| **Manuals** | `src/arangodb_mcp/manuals/*.md` | AQL reference, optimization guide, Cypher→AQL migration |

### 4.3 Key Design Patterns

| Pattern | Application |
|---------|-------------|
| **Agent-per-domain** | Each functional area has a dedicated agent class for testability and separation of concerns |
| **Decorator-based error handling** | `handle_arango_errors` in `agent_base.py` eliminates try/except boilerplate across all 15 agents. The decorator accepts an `on_arango_error: Callable[[Exception], dict \| None]` callback so agents like Cluster (single-server detection) and Backup (Enterprise-only detection) can rewrite specific error responses without hand-rolling try/except blocks. |
| **Async wrapper** | `ArangoAgentBase.run_sync()` wraps every synchronous python-arango call in `asyncio.to_thread()` so blocking driver I/O does not stall the FastMCP event loop. |
| **Tool-layer support (no-agent tools)** | The embedding / pattern-memory tools (§2.16–2.17) run directly in the tool layer without an agent. `src/arangodb_mcp/mcp_tools/_support.py` gives them the same two guarantees the agent base provides: `run_sync` (off-loop dispatch of blocking driver calls) and `arango_error_result` (the standardized `{error, error_code}` envelope). |
| **Bearer-token auth** | `auth_middleware.BearerTokenAuthMiddleware` is an ASGI middleware that wraps the FastMCP `streamable_http_app()` / `sse_app()` whenever `MCP_AUTH_TOKEN` is set, validating the `Authorization` header in constant time before forwarding the scope. |
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
| `ARANGO_VERIFY_SSL` | No | `true` | `ARANGO_` | Enable SSL certificate verification |
| `ARANGO_SSL_CERT_PATH` | No | `""` | `ARANGO_` | Path to SSL certificate file |
| `LOG_LEVEL` | No | `INFO` | — | Server log level |
| `LOG_FORMAT` | No | `text` | — | Log format: human-readable `text` or one-line `json` |
| `ENABLE_JS_TRANSACTIONS` | No | `false` | — | Enable server-side JavaScript transactions (security-sensitive) |
| `SERVER_NAME` | No | `ArangoDB MCP Server` | — | MCP server display name |
| `SERVER_VERSION` | No | `2.0.0` | — | MCP server version string |
| `MCP_TRANSPORT` | No | `stdio` | — | Transport protocol: `stdio`, `sse`, or `streamable-http` |
| `MCP_HOST` | No | `0.0.0.0` | — | Bind host for `sse`/`streamable-http` transport |
| `MCP_PORT` | No | `8000` | — | Bind port for `sse`/`streamable-http` transport |
| `MCP_AUTH_TOKEN` | Conditional | — | — | Bearer token required for `sse` / `streamable-http` transports. **REQUIRED** when `MCP_HOST` is non-loopback (anything other than `127.0.0.1`, `localhost`, or `::1`); the server exits with code `2` if unset in that configuration. Ignored for `stdio`. Stored in-process as `pydantic.SecretStr`. |
| `MCP_PROTOCOL_MODE` | No | `auto` | — | `strict` requires MCP 2026-07-28 request metadata, `auto` accepts complete v3 metadata or headerless legacy requests, and `legacy` disables metadata validation. |
| `MCP_DNS_REBINDING_PROTECTION` | No | `true` | — | Validate Host and Origin before MCP authentication or dispatch. |
| `MCP_ALLOWED_HOSTS` | No | local loopback hosts | — | Comma-separated Host allowlist; entries may use a `:*` port wildcard. |
| `MCP_ALLOWED_ORIGINS` | No | local HTTP loopback origins | — | Comma-separated browser Origin allowlist; entries may use a `:*` port wildcard. |
| `MCP_PROFILE` | No | `readonly` | — | Base exposure profile: `readonly`, `developer`, `operator`, or `admin`. |
| `MCP_TOOLSETS` | No | — | — | Comma-separated additive `graph` and/or `search` toolsets, bounded by the base profile operation class. |
| `MCP_DENIED_TOOLS` | No | — | — | Comma-separated exact tool names removed after profile resolution; unknown names fail startup. |
| `MCP_DENIED_CATEGORIES` | No | — | — | Comma-separated catalog categories removed after profile resolution; unknown categories fail startup. |
| `MCP_RESULT_CONTRACT` | No | `v3` | — | Versioned result contract; temporary `legacy` compatibility expires on 2027-02-01. |
| `MCP_LEGACY_ACTOR_ID` | No | `legacy-http` | — | Server-established actor for requests authenticated by the temporary shared-token mode. |
| `MCP_CONFIRMATION_SECRET` | Conditional | — | — | Server/operator-only HMAC key for out-of-band irreversible-action confirmation; never exposed through MCP. |
| `DEFAULT_AQL_MAX_RUNTIME` | No | `30` | — | Default per-query AQL max runtime, in seconds. Zero and oversized values are clamped to the non-disableable 30-second production ceiling. |
| `LOG_AQL_QUERIES` | No | `false` | — | Log the first 100 characters of user AQL; disabled by default to redact literals |
| `CONNECT_MAX_RETRIES` | No | `5` | — | Maximum transient connection retries at startup (`0` disables retries) |
| `CONNECT_INITIAL_BACKOFF` | No | `1.0` | — | Initial retry backoff in seconds, doubled up to 30 seconds |
| `OPENAI_API_KEY` | No | — | — | OpenAI API key for the embeddings endpoint (§2.16–2.17). Required for vector/hybrid `pattern-search` and for embedding new patterns; when unset those tools degrade to keyword-only (BM25) behaviour. Stored in-process as `pydantic.SecretStr`. |
| `EMBEDDING_MODEL` | No | `text-embedding-3-small` | — | OpenAI embedding model (1536 dimensions for the default). |

### 5.2 MCP Client Configuration

**stdio transport** (default) — the MCP client launches the server as a subprocess:

```json
{
  "mcpServers": {
    "arangodb-mcp": {
      "command": "arangodb-mcp",
      "args": [],
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

**HTTP transport** — for remote/Docker deployments, clients connect via URL:

```json
{
  "mcpServers": {
    "arangodb-mcp": {
      "url": "http://your-server:8000/mcp",
      "type": "http"
    }
  }
}
```

### 5.3 Standalone Deployment (Docker)

The server ships with a `Dockerfile` and `docker-compose.yml` for standalone deployment using
`streamable-http` transport. The multi-stage image builds the wheel, installs that wheel into an
isolated virtual environment, removes package installers, makes the installed environment
read-only, and runs as an unprivileged user. Local image success is not evidence of a published
immutable GHCR digest; that EXTERNAL gate remains open under DEP-003.

**Docker Compose** launches both the MCP server and an ArangoDB instance:

```bash
export ARANGO_ROOT_PASSWORD=your_password
export MCP_AUTH_TOKEN="$(openssl rand -hex 32)"
docker compose up -d
docker compose ps
curl --fail http://localhost:8000/healthz
```

Compose requires independent database and MCP secrets, enables ArangoDB's
`--experimental-vector-index` flag, and uses the database-backed MCP health endpoint. The MCP
endpoint is `http://localhost:8000/mcp` and requires
`Authorization: Bearer <MCP_AUTH_TOKEN>`; the ArangoDB UI is at `http://localhost:8529`.

**Docker only** (connect to existing ArangoDB):

```bash
docker build -t arangodb-mcp .
docker run -d -p 8000:8000 \
  -e ARANGO_HOSTS=http://your-arangodb:8529 \
  -e ARANGO_ROOT_USERNAME=root \
  -e ARANGO_ROOT_PASSWORD=your_password \
  -e MCP_AUTH_TOKEN="$(openssl rand -hex 32)" \
  arangodb-mcp
```

`MCP_AUTH_TOKEN` is required whenever the container binds to a non-loopback interface (the default for any container exposing port `8000`). Without it the server logs an error and exits with code `2` instead of starting an unauthenticated public listener. Clients must send `Authorization: Bearer <MCP_AUTH_TOKEN>` on every request.

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

The suite is organized into three tiers based on what infrastructure they need:

* **Mock** — pure-Python unit tests; run anywhere, no Docker, no ArangoDB.
* **E2E (framework)** — exercise the FastMCP server / tool registry by introspection; no live ArangoDB required.
* **Integration** — require a running ArangoDB instance (auto-provisioned by `conftest.py` via Docker, or supplied via `ARANGO_HOSTS`).

| Test File | Tier | Areas Covered |
|-----------|------|---------------|
| `test_connectivity.py` | Integration | Raw python-arango driver smoke tests (version, collections, docs, AQL, indexes) |
| `test_agents.py` | Integration | CollectionManagement, DocumentCRUD, IndexManagement, AQLExecution, ClusterManagement, GraphManagement |
| `test_aql_utils.py` | Mock | AQL identifier validation functions (injection vectors, edge cases) |
| `test_database_manual_analyzer.py` | Integration | DatabaseManagementAgent, ManualManagementAgent, AnalyzerManagementAgent |
| `test_vector_search.py` | Integration | VectorSearchAgent, ViewManagementAgent, IndexManagement (vector paths) |
| `test_traversal.py` | Integration | GraphTraversalAgent, AQL explain/validate |
| `test_transactions.py` | Integration | TransactionManagementAgent, BackupManagementAgent |
| `test_users.py` | Integration | UserManagementAgent (users + permissions, `SecretStr` password handling) |
| `test_cluster.py` | Integration (cluster) | Coordinator detection, DBServer count, sharding, replication; scheduled nightly against a pinned three-machine deployment |
| `test_agent_unit.py` | Mock | Per-agent unit tests with `arango_connector` patched out — covers logic branches in every agent without DB I/O |
| `test_arango_connector.py` | Mock | Connector configuration, retry, lifecycle, and health behavior |
| `test_base_and_decorator.py` | Mock | `ArangoAgentBase` (`resolve_db`, `pack_optional`, `run_sync`) and the `handle_arango_errors` decorator (specific exceptions, `on_arango_error` callback, fallthrough) |
| `test_app_factory.py` | ASGI contract | HTTP composition order, public liveness/metrics/RFC 9728 metadata, request/trace propagation, and pre-auth Host/Origin rejection |
| `test_deployment_contract.py` | Static contract | Compose, image health, quick-start, nightly cluster, and containerized Phase 4 identity/collector workflow invariants |
| `test_doc_consistency.py` | Static contract | Executable tool/test/config inventory matches README, PRD, and scorecard claims |
| `test_health_endpoint.py` | Mock | `/healthz`, JSON logging, and standalone HTTP database lifecycle |
| `test_mcp_tools.py` | Mock | Verifies each `@mcp_app.tool` wrapper builds the correct operation dict and delegates to its agent's `arun` |
| `test_embedding_tools.py` | Mock | `embed-text` / `embed-document` plus shared helpers — standardized errors, off-loop dispatch, TLS-env sanitisation, API-key guard, trace/header propagation, and dependency spans |
| `test_pattern_memory_tools.py` | Mock | The five shared-memory tools — BM25 fallback path, provenance upsert, usage bump + missing-key reporting, standardized errors, off-loop dispatch |
| `test_protocol_interop.py` | E2E (framework) | Pinned 2026-07-28 stateless initialize/list/call flow plus headerless 2025 compatibility |
| `test_protocol_metadata.py` | ASGI contract | MCP 2026-07-28 routing-header matching, Base64 sentinel decoding, unsupported-version errors, and legacy compatibility |
| `test_protocol_security.py` | ASGI contract | Official SDK Host and Origin allowlist behavior |
| `test_mcp_content.py` | MCP contract | Exact resources/templates/prompts inventory plus manual, schema, profile, status, and safe-workflow round trips |
| `test_quality_gates.py` | Quality | Blocking offline tool-selection, destructive-refusal, retrieval MRR/recall, and latency regression gates |
| `test_safety_policy.py` | Security | Parser-AST AQL classification, hard ceilings, confirmations, actor/global/class limits, retry metadata, trace hierarchy, and complete redacted mutation auditing |
| `test_security_contract.py` | Static contract | Secret scanning, built-image scanning, dependency audit, and severity/exception policy |
| `test_tool_policy.py` | Contract | Canonical 81-tool catalog completeness, exact profile inventories, additive toolsets, fail-closed denylists, and default `tools/list` token ceiling |
| `test_v3_contract.py` | Contract | Every registered tool dispatches through the v3 success/error envelope while input schema introspection and the dated legacy adapter remain valid |
| `test_mcp_e2e.py` | E2E (framework) | Imports `mcp_app`, introspects the tool registry, asserts tool count (81), schema shapes, and server instructions — without a live database |
| `test_coverage_gaps.py` | Integration | Fills gaps surfaced by review: document replace/bulk with read-back, ArangoSearch view CRUD, additional index types, hybrid search |
| `test_auth_middleware.py` | Mock | Legacy constant-time bearer compatibility plus OIDC signature/issuer/audience/time/claim validation, discovery/JWKS rotation, fail-closed errors, and identity context isolation |

### 6.3 CI/CD

| Component | Configuration |
|-----------|---------------|
| **Platform** | GitHub Actions (`ci.yml`) |
| **Triggers** | Push/PR to `main` |
| **Lint job** | Ruff check + Ruff format check + documentation consistency + deterministic quality gates + Mypy type check |
| **Test job** | pytest with coverage across Python 3.10 and 3.11, ArangoDB 3.12 Docker |
| **Security jobs** | CodeQL and dependency audit on push/PR, weekly schedule, and manual dispatch |
| **Cluster job** | Pinned three-machine ArangoDB Starter deployment and real cluster tests nightly/manual |
| **Phase 4 integration** | Containerized ephemeral-key reference IdP, Prometheus, and OTLP collector verify discovery/JWKS, signed JWT MCP access, metrics scraping, and trace export on every push/PR |
| **Package gate** | An isolated wheel-only install verifies the console script, all 81 tools, and packaged catalog/manual resources; the release workflow repeats this before publication |
| **Helm gate** | Strict lint/render and kubeconform run in CI; the local kind harness installs, probes, authenticates, upgrades, and re-probes the chart |
| **Release workflow** | Version tags matching `pyproject.toml` are configured for PyPI trusted publishing, GHCR digest publication, SBOM/provenance attestations, keyless signing, vulnerability scanning, and publication verification; no external release has completed yet |
| **Coverage** | `pytest-cov --cov=arangodb_mcp` measures the installable package and enforces the 79% floor |
| **PR exclusions** | `test_cluster.py` remains outside the normal PR matrix; it runs in the scheduled/manual cluster workflow |

---

## 7. Dependencies

### 7.1 Runtime

| Package | Version | Purpose |
|---------|---------|---------|
| `python` | ^3.10 | Language runtime |
| `python-arango` | ^8.1 | ArangoDB Python driver |
| `mcp` | ^1.0 | Model Context Protocol SDK |
| `pydantic` | ^2.0 | Data validation and serialization |
| `pydantic-settings` | ^2.0 | Environment-based configuration |
| `anyio` | ^4.5 | Async I/O compatibility |
| `httpx` | ^0.28 | OIDC/JWKS and embedding HTTP client |
| `pyjwt[crypto]` | ^2.13 | Asymmetric OIDC access-token verification |
| `prometheus-client` | ^0.26 | Bounded-cardinality metrics and ASGI exposition |
| `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http` | ^1.44 | Trace API, SDK, and OTLP/HTTP export |
| `pyyaml` | ^6.0 | Canonical tool-catalog loading |

### 7.2 Development

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | ^9.1 | Test framework |
| `pytest-asyncio` | ^1.4 | Async test support |
| `pytest-timeout` | ^2.2 | Test timeout enforcement |
| `black` | ^26.5 | Legacy compatibility formatter; CI uses Ruff |
| `isort` | ^5.13 | Legacy compatibility import sorter; CI uses Ruff |
| `mypy` | ^1.0 | Static type checker |
| `ruff` | ^0.8 | Fast linter and formatter |
| `pytest-cov` | ^7.1 | Test coverage reporting and 79% floor enforcement |
| `pip-audit` | ^2.10 | Dependency vulnerability audit |

### 7.3 Packaging and distribution

The application uses a `src/` layout and installs as the `arangodb_mcp` package. The
`arangodb-mcp` console script resolves to `arangodb_mcp.cli:main`; the canonical tool catalog and
three manuals are wheel data. `scripts/verify_wheel.py` proves the wheel from a temporary
environment with the repository absent from `sys.path`. The configured release workflow can
publish the wheel, a digest-addressed container, SBOMs, attestations, signature, and Helm chart,
but DEP-003 and MAT-001 remain PARTIAL until those artifacts exist externally.

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
| Async-safety & auth | `09a2eb1`–`e942878` | Async-safety pass: `run_sync` wrapping across all 15 agents; `@handle_arango_errors` adopted by remaining 2 agents (Cluster, Backup) with the new `on_arango_error` callback for Enterprise / cluster-mode rewrites; HTTP bearer-token auth (`auth_middleware.BearerTokenAuthMiddleware`) plus non-loopback startup guard; `MCP_AUTH_TOKEN` and `DEFAULT_AQL_MAX_RUNTIME` settings added; `SecretStr` extended to user-create / user-update passwords; orphan config fields (`max_connections`, `timeout`, `enable_metrics`) removed; broken docker-test cluster mode removed. |
| Shared-memory tooling | `01583ae`–`fbb2b1b` | Embedding tools (`embed-text`, `embed-document`) and shared-memory pattern/drift tools (`pattern-search`, `save-pattern`, `pattern-index`, `pattern-applied`, `save-drift-alert`) — **7 tools, 81 total** (PRD §2.16–2.17); auto-create target database; graph provenance on the write path. Async-safety + standardized-error retrofit via `src/arangodb_mcp/mcp_tools/_support.py`; embedding config (`OPENAI_API_KEY`, `EMBEDDING_MODEL`); unit tests `test_embedding_tools.py` + `test_pattern_memory_tools.py`. |

### 8.2 Adding New Tools

1. Create an agent in `src/arangodb_mcp/agents/` inheriting from `ArangoAgentBase`.
2. Use `self.resolve_db(...)` to get an authenticated `(db, resolved_db_name)` tuple instead of touching `arango_connector` directly.
3. Wrap every blocking python-arango call in `await self.run_sync(...)` so the call runs in a thread and does not block the FastMCP event loop.
4. Apply `@handle_arango_errors` to `arun` for standard error handling. If the agent needs to rewrite specific ArangoDB errors (e.g. Enterprise-only or cluster-only paths), pass an `on_arango_error` callback that returns a custom dict for the cases it wants to override and `None` to fall through to the standard error envelope.
5. Create tool definitions in `src/arangodb_mcp/mcp_tools/` using `@mcp_app.tool` with Pydantic `Field` descriptions; for any password / secret parameter, use `pydantic.SecretStr` so values are not echoed in logs.
6. Import the new tool module in both `src/arangodb_mcp/mcp_tools/__init__.py` and `src/arangodb_mcp/server.py`.
7. Add tests in `tests/` — at minimum a mock-based unit test in `test_agent_unit.py` and, for the wrapper, a delegation test in `test_mcp_tools.py`.
8. Update the tool-count claims in `src/arangodb_mcp/server.py`, `PRD.md`, and `README.md`, then run
   `poetry run python scripts/verify_docs.py` to reconcile executable inventories.

---

## 9. Known Limitations & Future Work

### 9.1 Current Limitations

| Area | Limitation |
|------|-----------|
| **Legacy authorization mode** | The temporary `MCP_AUTH_TOKEN` compatibility mode retains one configured database identity. Production multi-actor HTTP deployments use OIDC scope/profile/catalog intersection, token/server database allowlists, and server-resolved request credentials. |
| **Connection pooling** | Driver pool/timeout tuning not yet exposed via configuration |
| **Telemetry backend operations** | Metrics and OTLP export are implemented; long-term storage, dashboards, alert routing, and collector high availability remain deployment-operator responsibilities. |
| **Cluster CI evidence** | Nightly/manual real-cluster workflow is active; [run 31068063574](https://github.com/arango-solutions/arango-solutions-mcp/actions/runs/31068063574) passed against the pinned three-machine deployment on 2026-08-05. |
| **Artifact publication** | Wheel and immutable non-root image verification pass locally, but no PyPI or GHCR release artifact is externally published. |
| **Release attestations** | Trusted publishing, SBOM, provenance, keyless signing, and verification are configured but have no external release evidence yet. |
| **Governance publication** | Security, contribution, ownership, threat-model, support, and deprecation files exist locally but are not yet public. |
| **Scorecard regrade** | Phase 4/5 improvements remain uncredited until an independent MAT-003 rerun after at least 30 days of required green and external evidence. |

### 9.2 Planned Features (per branch history)

| Feature | Branch | Status |
|---------|--------|--------|
| User & permission management | `feature/user-permission-management` | **Merged** to `main` |
| HTTP transport mode | `feature/http-mode` | **Implemented + auth gating** (streamable-http + SSE via `MCP_TRANSPORT`, with `MCP_AUTH_TOKEN` bearer-token middleware and a non-loopback startup guard) |
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
