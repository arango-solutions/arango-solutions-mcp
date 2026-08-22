# ArangoDB MCP Server

A comprehensive [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server for ArangoDB, with a canonical catalog of **81 tools** covering document CRUD, graph traversals, AQL queries, vector/semantic search, cluster administration, stream transactions, hot backup, user/permission management, and more. Version 3 exposes a compact 17-tool readonly profile by default; broader access is explicit. The catalog also includes a **shared-memory pattern layer** (`pattern-search` hybrid retrieval, `save-pattern`, `pattern-index`, `pattern-applied` with outcome tracking, `save-drift-alert`, and `embed-text`/`embed-document` via OpenAI embeddings; these degrade gracefully to keyword-only when `OPENAI_API_KEY` is unset). Writes are attributed to the connected ArangoDB user. See `PRD.md` for the full tool contract.

Built for AI assistants (Cursor, Claude Desktop, etc.) that need full-spectrum access to ArangoDB's multi-model capabilities.

## Supported ArangoDB Versions

- **ArangoDB 3.12+** (vector search requires 3.12.4+ with `--experimental-vector-index`)
- **ArangoDB 4.0** (under development — forward-compatible)

## Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management
- ArangoDB instance (local, Docker, or remote)

## Quick Start

### 1. Install

For source development, clone the repository and install the package:

```bash
poetry install --with dev
poetry run arangodb-mcp --version
```

After the first external release is published, the wheel install will be:

```bash
python -m pip install arangodb-mcp-server
arangodb-mcp --version
```

The wheel and console entry point pass the local isolated-install gate, but no PyPI distribution is
published as of this documentation audit.

### 2. Configure Your MCP Client

**Cursor IDE** — edit `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "arangodb-mcp": {
      "command": "arangodb-mcp",
      "args": [],
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
      "command": "arangodb-mcp",
      "args": [],
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

**Antigravity** — edit `~/.gemini/antigravity/mcp_config.json` (or use the MCP Store UI → "View raw config"):

```json
{
  "mcpServers": {
    "arangodb-mcp": {
      "command": "arangodb-mcp",
      "args": [],
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

For remote/Docker deployments, Antigravity can connect via HTTP:

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

### 3. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ARANGO_HOSTS` | Yes | — | ArangoDB server URL(s) |
| `ARANGO_ROOT_USERNAME` | Yes | — | ArangoDB username |
| `ARANGO_ROOT_PASSWORD` | Yes | — | ArangoDB password |
| `ARANGO_DEFAULT_DB_NAME` | No | `_system` | Default database name |
| `ARANGO_VERIFY_SSL` | No | `true` | Verify SSL certificates |
| `ARANGO_SSL_CERT_PATH` | No | — | Path to SSL certificate file |
| `SERVER_NAME` | No | `ArangoDB MCP Server` | MCP server display name |
| `SERVER_VERSION` | No | `2.0.0` | MCP server version string |
| `LOG_LEVEL` | No | `INFO` | Server log level |
| `LOG_FORMAT` | No | `text` | `text` or one-line `json` structured logs |
| `ENABLE_JS_TRANSACTIONS` | No | `false` | Enable server-side JavaScript transactions (security-sensitive) |
| `MCP_TRANSPORT` | No | `stdio` | Transport protocol: `stdio`, `sse`, or `streamable-http` |
| `MCP_HOST` | No | `0.0.0.0` | Bind host for `sse`/`streamable-http` transport |
| `MCP_PORT` | No | `8000` | Bind port for `sse`/`streamable-http` transport |
| `MCP_AUTH_TOKEN` | Conditional | — | Legacy static bearer token. Set this or `MCP_OIDC_ISSUER` for a non-loopback HTTP bind, never both. |
| `MCP_OIDC_ISSUER` | Conditional | — | Exact OIDC issuer URL; enables provider-neutral JWT resource-server mode |
| `MCP_OIDC_AUDIENCE` | With OIDC | — | Required JWT `aud` value |
| `MCP_RESOURCE_URL` | With OIDC | — | Canonical protected-resource URL advertised by RFC 9728 metadata |
| `MCP_OIDC_ALGORITHMS` | No | `RS256` | Comma-separated asymmetric JWT signing algorithms; symmetric `HS*` algorithms are rejected |
| `MCP_OIDC_ACTOR_CLAIM` | No | `sub` | Validated JWT claim used as the request actor |
| `MCP_OIDC_DATABASE_CLAIM` | No | `arangodb_databases` | JWT list claim that narrows the actor's server-side database allowlist |
| `MCP_OIDC_CLOCK_SKEW_SECONDS` | No | `30` | Expiry and not-before validation leeway (maximum 300 seconds) |
| `MCP_OIDC_CACHE_TTL_SECONDS` | No | `300` | Fallback discovery/JWKS cache lifetime; HTTP `max-age` is honored up to one hour |
| `MCP_OIDC_ALLOW_INSECURE_HTTP` | No | `false` | Test/development-only HTTP escape hatch limited to loopback, private IPs, single-label container DNS, and `.test`/`.local`; production remains HTTPS-only |
| `MCP_ARANGO_CREDENTIALS_JSON` | With OIDC | — | Secret server-side actor credential mapping; tokens cannot supply usernames or passwords |
| `MCP_PROTOCOL_MODE` | No | `auto` | `strict` requires MCP 2026-07-28 request metadata, `auto` accepts complete v3 metadata or headerless legacy requests, and `legacy` disables metadata validation |
| `MCP_DNS_REBINDING_PROTECTION` | No | `true` | Validate the MCP `Host` and browser `Origin` headers |
| `MCP_ALLOWED_HOSTS` | No | local loopback hosts | Comma-separated Host allowlist; `:*` permits any port |
| `MCP_ALLOWED_ORIGINS` | No | local HTTP loopback origins | Comma-separated browser Origin allowlist; `:*` permits any port |
| `MCP_PROFILE` | No | `readonly` | Base exposure profile: `readonly`, `developer`, `operator`, or `admin` |
| `MCP_TOOLSETS` | No | — | Comma-separated additive `graph` and/or `search` toolsets; additions never bypass the base profile's operation class |
| `MCP_DENIED_TOOLS` | No | — | Comma-separated exact tool names removed after profile resolution; unknown names fail startup |
| `MCP_DENIED_CATEGORIES` | No | — | Comma-separated catalog categories removed after profile resolution; unknown categories fail startup |
| `MCP_RESULT_CONTRACT` | No | `v3` | `v3` returns the versioned envelope; temporary `legacy` preserves prior result shapes until 2027-02-01 |
| `MCP_LEGACY_ACTOR_ID` | No | `legacy-http` | Server-established actor bound to requests authenticated by the temporary shared bearer token |
| `MCP_CONFIRMATION_SECRET` | Conditional | — | Server/operator-only HMAC key for minting irreversible-action confirmations; required to execute catalog entries with `confirmation: human` and never sent to MCP clients |
| `METRICS_ENABLED` | No | `true` | Expose the bounded-cardinality Prometheus scrape route |
| `METRICS_PATH` | No | `/metrics` | Prometheus scrape path |
| `OTEL_TRACES_EXPORTER` | No | `none` | `none` or OTLP over HTTP/protobuf |
| `OTEL_SERVICE_NAME` | No | `arangodb-mcp-server` | OpenTelemetry service name |
| `OTEL_SERVICE_VERSION` | No | `2.0.0` | OpenTelemetry service version |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | `http://localhost:4318` | OTLP/HTTP collector base URL; `/v1/traces` is appended when absent |
| `OTEL_EXPORTER_OTLP_HEADERS` | No | — | Secret comma-separated OTLP `key=value` headers |
| `OTEL_EXPORTER_OTLP_TIMEOUT_SECONDS` | No | `10` | OTLP export timeout |
| `MCP_ACTOR_RATE_LIMIT_PER_MINUTE` | No | `600` | Token refill rate applied independently to each server-established actor |
| `MCP_ACTOR_RATE_LIMIT_BURST` | No | `200` | Maximum burst tokens retained per actor |
| `MCP_GLOBAL_MAX_CONCURRENCY` | No | `64` | Process-wide concurrent tool execution ceiling |
| `MCP_CLASS_CONCURRENCY_LIMITS` | No | `standard=32,query=16,bulk=8,control=4,external=8` | Catalog limit-class concurrency ceilings |
| `MCP_LIMITER_RETRY_AFTER_MS` | No | `250` | Retry hint for rejected global/class/tool concurrency |
| `DEFAULT_AQL_MAX_RUNTIME` | No | `30.0` | Default per-query AQL max runtime in seconds. Zero and values above 30 are clamped to the non-disableable 30-second production ceiling. |
| `LOG_AQL_QUERIES` | No | `false` | Whether to log the first 100 chars of user-supplied AQL. Default `false` because inline literals (`FILTER doc.token == "abc"`) can contain secrets. When `false`, the agent logs `<redacted len=N sha1=…>` instead. |
| `CONNECT_MAX_RETRIES` | No | `5` | Maximum transient connection retries at startup (`0` disables retries) |
| `CONNECT_INITIAL_BACKOFF` | No | `1.0` | Initial retry backoff in seconds, doubled up to 30 seconds |
| `STARTUP_CONNECT_BUDGET` | No | `8.0` | Seconds to spend on the initial ArangoDB connection before serving anyway. Keep well under the MCP client handshake ceiling (Claude Code: 30s) — a startup connect that outlives it never answers `initialize`, so the client drops every tool instead of reporting a database problem |
| `OPENAI_API_KEY` | No | — | OpenAI API key for the embedding tools (`embed-*`, `pattern-search` vector mode, `save-pattern`). When unset, the pattern tools degrade to keyword-only (BM25). Stored as `SecretStr`. |
| `EMBEDDING_MODEL` | No | `text-embedding-3-small` | OpenAI embedding model (1536 dimensions for the default). |

All tools accept an optional `database_name` parameter to override the default.

#### Tool profiles and result contract

The packaged `src/arangodb_mcp/catalog/tools.yaml` is the startup source of truth for all 81 tools. Every entry declares its
category, risk tier, read/write/admin class, scope, limit policy, and confirmation policy. Startup
fails if code registers an unknown tool or if a catalog entry is not registered.

The default `readonly` profile exposes 17 read-only database inspection tools. `developer` adds
write-class tools, `operator` adds operational/admin controls except identity management, and
`admin` exposes the complete catalog. The `graph` and `search` toolsets are additive and remain
bounded by the base profile's operation classes. `MCP_DENIED_TOOLS` and
`MCP_DENIED_CATEGORIES` always subtract from the resolved inventory; denied tools are neither
listed nor executable.

Every MCP-dispatched tool result uses this v3 shape:

```json
{
  "contractVersion": "3.0",
  "status": "success",
  "data": {},
  "error": null,
  "meta": {"tool": "list-collections"}
}
```

Errors use the same fields with `status: "error"`, `data: null`, and a machine-readable
`error.code`/`error.message`. `MCP_RESULT_CONTRACT=legacy` temporarily preserves the v2 shape
without changing tool input schemas; the adapter refuses to run on or after 2027-02-01.

#### Parser-backed AQL policy, hard ceilings, and confirmations

Before execution, `execute-aql-query` calls ArangoDB's `POST /_api/query` parser through
`db.aql.validate` and classifies the returned AST as `read`, `mutation`, or `ambiguous`. Readonly
mode fails closed on mutation and ambiguity; text regexes are not used. In write-capable profiles,
AST mutation nodes (`insert`, `update`, `replace`, `remove`, and `upsert`) require a human
confirmation before execution. Dynamic `CALL`/`APPLY` and user-defined function calls are
ambiguous.

The dispatch boundary enforces code-level ceilings that configuration cannot disable:

- runtime: at most 120 seconds per tool and 30 seconds for AQL;
- rows: at most 1,000 known row-bearing items, with explicit truncation metadata;
- response: at most 2 MiB, otherwise a machine-readable denial;
- bulk input: at most 1,000 items in any input array; and
- concurrency: at most 16 calls per tool, with lower catalog policies and retry metadata.

Catalog entries with `confirmation: human` expose a required `confirmation_token` argument but no
MCP tool can mint it. A trusted operator sets `MCP_CONFIRMATION_SECRET` only in the server/operator
environment and mints a token bound to the authenticated actor, exact tool, canonical parameters,
and a maximum five-minute expiry:

```bash
MCP_CONFIRMATION_SECRET='operator-secret' poetry run python scripts/mint_confirmation.py \
  --actor legacy-http \
  --action delete-document \
  --arguments-json '{"collection_name":"users","document_key_or_id":"42"}'
```

The token is consumed atomically on first use; changed actor/action/parameters, expiry, or replay
is denied before the tool function runs.

#### Operations telemetry, audit, and limits

HTTP responses return a safe `X-Request-ID` and W3C `traceparent`; accepted incoming values retain
their correlation, while invalid request IDs are replaced. Stdio tool dispatch creates the same
request/trace context. The context follows `asyncio.to_thread` worker calls and is sent to the
embedding provider as `X-Request-ID` plus `traceparent`. Text and JSON logs include both IDs.

`GET /metrics` exposes tool count/duration/error, AQL runtime, ArangoDB/embedding call and in-flight
pressure, and limiter state/rejection metrics. Label values are limited to catalog tool names and
fixed operation/outcome/dependency/limit classes; actor IDs, database names, query text, and error
messages are never labels.

Set `OTEL_TRACES_EXPORTER=otlp` to export OTLP HTTP/protobuf traces. The pinned
`arangodb-mcp/1.0` convention emits `mcp.request` → `mcp.tool.call` → `arango.database` and
`dependency.embedding` spans. Every catalog `write` or `admin` dispatch attempt emits exactly one
allow-listed `audit.catalog` event containing actor, action, identifier-only target, outcome,
request correlation ID, and trace ID. Passwords, access/confirmation tokens, AQL, and document
payloads are not copied into audit events.

Per-actor token buckets and atomic global/catalog-class/per-tool concurrency ceilings reject before
execution. V3 responses place the machine-readable limit and `retry_after_ms` under
`meta.policy.limit`; limiter gauges and rejection counters are exported on `/metrics`.

#### Containerized Phase 4 acceptance harness

Run the same OIDC and telemetry acceptance flow used by CI:

```bash
python3 scripts/run_phase4_integration.py --timeout 300
```

`docker-compose.phase4.yml` builds a repository-owned reference IdP, generates its RSA signing key
only in container memory at runtime, and performs real discovery, JWKS retrieval, and signed JWT
validation through the MCP HTTP service. It also starts pinned
`otel/opentelemetry-collector-contrib:0.123.0` and `prom/prometheus:v3.2.1` images. The runner uses
available loopback host ports, waits with bounded timeouts, verifies the Prometheus target/tool
metric and collector span output, prints service logs on failure, and always removes containers and
volumes unless `--keep` is supplied.

The harness alone sets `MCP_OIDC_ALLOW_INSECURE_HTTP=true` because Docker service discovery uses
plain HTTP on an isolated bridge. The default remains `false`; even when enabled, HTTP is restricted
to loopback/private addresses, single-label container DNS, and `.test`/`.local` names. Deployments
must use HTTPS issuers and resources.

#### MCP resources, prompts, and quality gates

Clients can read `arangodb://profile`, `arangodb://schema`, `arangodb://status`, and
`arangodb://manuals/{aql_ref|optimization|cypher2aql}`. The registered prompts
`safe-aql-workflow`, `safe-graph-workflow`, and `safe-search-workflow` generate bounded,
policy-aware workflows.

`poetry run python evals/run_quality_gates.py --check` runs without model APIs. CI requires
tool-selection accuracy ≥90%, destructive refusal 100%, retrieval MRR@10 ≥0.90, recall@5 1.0,
and the committed p50/p95/p99 latency ceilings in `evals/baselines/quality.v1.json`.

#### HTTP transport security

When `MCP_TRANSPORT=streamable-http` or `sse` and `MCP_HOST` is non-loopback (e.g.
`0.0.0.0`), configure exactly one HTTP authentication mode. The server refuses to start without
one, or with both modes configured.

- `MCP_AUTH_TOKEN` preserves the legacy shared bearer behavior and constant-time comparison.
- `MCP_OIDC_ISSUER` enables the production resource-server mode. It requires
  `MCP_OIDC_AUDIENCE`, `MCP_RESOURCE_URL`, and `MCP_ARANGO_CREDENTIALS_JSON`.

OIDC mode fetches the provider's standard discovery document and JWKS, validates asymmetric JWT
signatures plus exact issuer, audience, expiry, and not-before, and refreshes JWKS on cache expiry
or an unknown `kid` during key rotation. `GET /.well-known/oauth-protected-resource` and the
resource-path form (for example `/.well-known/oauth-protected-resource/mcp`) expose RFC 9728
metadata without authentication.

The JWT `scope` claim uses operation authorities `mcp:read`, `mcp:write`, and `mcp:admin`.
These names are independent of the catalog's `scope` field. Visible and executable tools are the
intersection of token operation scope, startup profile/toolsets, denylists, and canonical catalog
policy. The JWT database claim can only narrow the databases in the trusted server mapping:

```json
{
  "alice": {
    "username": "alice_mcp",
    "password_env": "ARANGO_ALICE_PASSWORD",
    "databases": ["tenant_a"]
  }
}
```

Passwords are resolved from server configuration or the named server environment variable; JWT
password/user claims are ignored. Each request receives an isolated actor, OAuth-scope set,
effective database allowlist, and least-privilege ArangoDB credential. Missing mappings, empty
authority intersections, unknown signing keys, invalid claims, and dependency failures fail closed
with structured errors. Loopback binds without either mode remain available for local development
and log a warning.

Streamable HTTP is stateless. `MCP_PROTOCOL_MODE=strict` requires the 2026-07-28
`MCP-Protocol-Version`, `Mcp-Method`, and applicable `Mcp-Name` headers to match the JSON-RPC
body. The default `auto` mode enforces the complete v3 contract when any routing header is
present but temporarily accepts headerless legacy clients. `MCP_ALLOWED_HOSTS` and
`MCP_ALLOWED_ORIGINS` must include public deployment names; Host and Origin validation occurs
before bearer authentication. The official Python SDK currently advertises 2025-11-25, so
`protocol_compat.py` provides a tested negotiation bridge with a hard 2027-02-01 sunset; it is
removed automatically from the design once upstream natively advertises 2026-07-28.

> **Limitation:** the auth middleware wraps the official MCP SDK's ASGI app factories
> (`streamable_http_app()` / `sse_app()`). If a future SDK release removes those factories, the
> server refuses to start when HTTP authentication is configured rather than silently disable it (exit
> code `3`).

#### Health probes

The HTTP transports expose three unauthenticated, exact-path, `GET`-only probes. Probe responses
are JSON with `Cache-Control: no-store`; other MCP paths remain bearer-authenticated.

- `GET /livez` is process liveness. It returns `200 {"status":"alive"}` without calling ArangoDB.
  Use it only to decide whether the process should be restarted.
- `GET /readyz` is dependency-aware readiness. It checks the configured ArangoDB database and
  returns `200` with `status: "ready"` when usable, or `503` with `status: "not_ready"` when the
  dependency is unavailable or the connector is not initialized. Use it for traffic admission and
  container health.
- `/healthz` is a deprecated `GET` compatibility alias for `/readyz`. It has the same status code and
  body and adds standards-based `Deprecation` and successor `Link` response headers. New
  integrations must use `/readyz`.

See [`docs/slo.md`](docs/slo.md) for the initial SLO, measurement window, startup handling, and
probe timing contract.

---

## Standalone Deployment (Docker)

The server can run as a standalone service using `streamable-http` or `sse` transport, accessible by any MCP client over the network.

### Docker Compose (recommended)

Launches both the MCP server and an ArangoDB instance:

```bash
# Set independent database and MCP credentials
export ARANGO_ROOT_PASSWORD=your_password
export MCP_AUTH_TOKEN="$(openssl rand -hex 32)"

# Start the stack
docker compose up -d

# Wait for both containers to report healthy
docker compose ps
curl --fail http://localhost:8000/livez
curl --fail http://localhost:8000/readyz
```

Compose refuses to start when the database secret is missing, and the MCP process refuses a public
bind unless either legacy bearer or OIDC configuration is complete. The bundled ArangoDB service
enables `--experimental-vector-index`, and the MCP image health check probes the database-backed
`/readyz` endpoint. The MCP endpoint is `http://localhost:8000/mcp`; clients must send
`Authorization: Bearer <access-token>`. The ArangoDB UI is available at
`http://localhost:8529`. Set `MCP_HTTP_PORT` or `ARANGO_HTTP_PORT` before startup when those host
ports are already in use.

### Docker only (connect to existing ArangoDB)

```bash
docker build -t arangodb-mcp .

docker run -d -p 8000:8000 \
  -e ARANGO_HOSTS=http://your-arangodb:8529 \
  -e ARANGO_ROOT_USERNAME=root \
  -e ARANGO_ROOT_PASSWORD=your_password \
  -e ARANGO_DEFAULT_DB_NAME=myapp \
  -e MCP_AUTH_TOKEN="$(openssl rand -hex 32)" \
  arangodb-mcp
```

Either `MCP_AUTH_TOKEN` or complete OIDC configuration is required whenever the container binds to
a non-loopback interface (the default for a published port); the server exits with code `2` instead
of starting an unauthenticated public listener. See "HTTP transport security" above.

The multi-stage build installs only the project wheel and locked runtime dependencies, removes
package installers, makes the installed environment read-only, and runs as an unprivileged user.
This local image contract is verified; pinning `image.digest` requires a published GHCR artifact,
which does not yet exist.

## Kubernetes Deployment (Helm)

The supported chart is [`deploy/helm/arangodb-mcp`](deploy/helm/arangodb-mcp). It provides
legacy bearer and OIDC modes, existing-Secret wiring, hardened Pod defaults, `/livez` and
`/readyz` probes, resource controls, optional Ingress/ServiceMonitor/PDB, and scheduling controls.
The chart deploys only this server; configure `arango.hosts` for an independently operated
ArangoDB service.

Production defaults never embed credentials. Create or externally manage a Kubernetes Secret and
set `secrets.existingSecret`. Chart-created Secrets are explicitly opt-in for disposable
development only because Helm release history retains supplied values. Pin published images with
`image.digest`; see the [chart README](deploy/helm/arangodb-mcp/README.md) for OIDC mappings,
Secret keys, install commands, hardening details, and upgrade/rollback guidance.

Validate the chart and run the disposable kind install/upgrade acceptance test with:

```bash
scripts/install_helm_tools.sh  # pinned Linux x86_64 / macOS arm64 toolchain
scripts/verify_helm.sh
scripts/run_helm_kind_smoke.sh # requires Docker and kubectl
```

### Without Docker

```bash
MCP_TRANSPORT=streamable-http \
MCP_PORT=8000 \
ARANGO_HOSTS=http://localhost:8529 \
ARANGO_ROOT_USERNAME=root \
ARANGO_ROOT_PASSWORD=your_password \
  poetry run arangodb-mcp
```

The server exposes the MCP endpoint at `http://localhost:8000/mcp`. Any MCP client that supports HTTP transport can connect to it.

To run the focused probe contract against an already-running server (the probe requests deliberately
omit authorization):

```bash
MCP_PROBE_BASE_URL=http://localhost:8000 \
  poetry run pytest tests/test_health_endpoint.py::test_readiness_alias_contract_in_process_or_live -v
```

---

## Tools (81)

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

*Requires ArangoDB 3.12.4+ with `--experimental-vector-index` enabled.*

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

### Embeddings (2)

Optional — require `OPENAI_API_KEY`; the pattern tools degrade to keyword-only when it is unset.

| Tool | Description |
|------|-------------|
| `embed-text` | Generate OpenAI embedding vectors for text strings (programmatic callers) |
| `embed-document` | Embed a document's fields and store the vector on it server-side |

### Shared-Memory Patterns & Drift (5)

Cross-project "dark factory" memory: reusable solution patterns and PRD-drift alerts, retrieved by hybrid semantic search. Writes are attributed to the connected ArangoDB user.

| Tool | Description |
|------|-------------|
| `pattern-search` | Hybrid vector + BM25 search over shared patterns (RRF k=10, multiplicative salience) |
| `save-pattern` | Embed-then-insert a solved-problem pattern; maintains provenance + `relates_to` edges |
| `pattern-index` | Backfill the embedding and graph edges for one saved pattern |
| `pattern-applied` | Record that a pattern was reused, with an `outcome` (`worked`/`failed`) that feeds ranking |
| `save-drift-alert` | Upsert a PRD drift alert linked to its project |

---

## Architecture

```
arango-solutions-mcp/
├── src/arangodb_mcp/        # Installable application package
│   ├── cli.py               # Configuration-free console/version entry point
│   ├── main.py              # Server bootstrap and event loop setup
│   ├── server.py            # FastMCP app and registration boundary
│   ├── mcp_content.py       # MCP resources and safe workflow prompts
│   ├── config.py            # Pydantic settings (env-based, zero hardcoding)
│   ├── arango_connector.py  # Connection pool, SSL, lifespan management
│   ├── oidc.py              # OIDC validation, JWKS rotation, RFC 9728 metadata
├── docker-compose.phase4.yml # Containerized OIDC/Prometheus/OTLP acceptance
├── scripts/
│   └── run_phase4_integration.py
│
│   ├── asgi/                # HTTP app composition and health routing
│   ├── app_factory.py
│   └── health.py
│   ├── middleware/          # Protocol, transport-security, request context
│   ├── protocol.py
│   ├── request_context.py
│   └── transport_security.py
│   ├── catalog/             # Canonical 81-tool policy metadata (packaged data)
│   ├── loader.py
│   └── tools.yaml
│   ├── policy/              # Profiles, denylists, filtered dispatch
│   ├── actor_context.py
│   ├── aql_classifier.py
│   ├── confirmation.py
│   ├── context.py
│   ├── credentials.py
│   ├── limits.py
│   ├── profiles.py
│   └── tool_manager.py
│   ├── contracts/           # Versioned public result envelopes
│   └── v3_result.py
├── evals/                   # Offline selection/refusal/retrieval gates
│   ├── data/
│   ├── baselines/
│   ├── ranking.py
│   └── run_quality_gates.py
│
│   ├── agents/              # Business logic layer
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
│   ├── mcp_tools/           # MCP tool definitions (thin wrappers → agents)
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
│   ├── manual_tools.py
│   ├── embedding_tools.py
│   ├── pattern_memory_tools.py
│   └── _support.py
│
│   ├── observability/       # Correlation, metrics, tracing, and audit
│   ├── audit.py
│   ├── context.py
│   ├── conventions.py
│   ├── dependencies.py
│   ├── http.py
│   ├── metrics.py
│   └── telemetry.py
│
├── tests/                   # Pytest suite (431 test functions)
│   ├── conftest.py          # Auto-provisions Docker containers
│   ├── test_app_factory.py
│   ├── test_connectivity.py
│   ├── test_agents.py
│   ├── test_agent_unit.py
│   ├── test_aql_utils.py
│   ├── test_arango_connector.py
│   ├── test_auth_middleware.py
│   ├── test_base_and_decorator.py
│   ├── test_coverage_gaps.py
│   ├── test_database_manual_analyzer.py
│   ├── test_deployment_contract.py
│   ├── test_doc_consistency.py
│   ├── test_embedding_tools.py
│   ├── test_health_endpoint.py
│   ├── test_mcp_e2e.py
│   ├── test_mcp_content.py
│   ├── test_mcp_tools.py
│   ├── test_pattern_memory_tools.py
│   ├── test_protocol_interop.py
│   ├── test_protocol_metadata.py
│   ├── test_protocol_security.py
│   ├── test_quality_gates.py
│   ├── test_safety_policy.py
│   ├── test_security_contract.py
│   ├── test_tool_policy.py
│   ├── test_v3_contract.py
│   ├── test_vector_search.py
│   ├── test_traversal.py
│   ├── test_transactions.py
│   ├── test_users.py
│   └── test_cluster.py
│
│   └── manuals/             # Packaged AQL reference documents
```

The codebase follows a two-layer pattern:

- **MCP Tools** (`src/arangodb_mcp/mcp_tools/`) — thin FastMCP-decorated functions that validate inputs and delegate to agents.
- **Agents** (`src/arangodb_mcp/agents/`) — business logic classes inheriting from `ArangoAgentBase` that interact with ArangoDB via `python-arango`.

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

Cluster-specific tests require a real multi-server deployment:

```bash
ARANGO_HOSTS=http://localhost:8529 \
ARANGO_ROOT_USERNAME=root \
ARANGO_ROOT_PASSWORD=your_password \
  poetry run pytest tests/test_cluster.py -m cluster -v
```

`.github/workflows/cluster-nightly.yml` provisions a pinned three-machine local cluster with
ArangoDB Starter and runs this tier nightly. The normal PR matrix continues to use a single server.

### Linting & Formatting

```bash
poetry run ruff check .         # lint
poetry run ruff format --check . # format check (use without --check to auto-fix)
poetry run python -m mypy \
  --ignore-missing-imports --no-error-summary \
  --disable-error-code=union-attr --disable-error-code=no-any-return \
  --disable-error-code=no-untyped-def --disable-error-code=call-arg \
  --disable-error-code=arg-type --disable-error-code=operator \
  --disable-error-code=assignment \
  src/arangodb_mcp evals/
poetry run python scripts/verify_docs.py
poetry run python scripts/verify_wheel.py
scripts/verify_helm.sh
```

### Packaging and releases

`scripts/verify_wheel.py` builds a wheel, creates a temporary virtual environment outside the
repository, installs only that wheel and its declared dependencies, clears `PYTHONPATH`, runs the
probe with Python isolated mode, verifies all 81 tool registrations plus packaged catalog/manual
data, and exercises `arangodb-mcp --version`. This is the required local packaging gate.

Pushing a version tag matching `v<pyproject-version>` starts `.github/workflows/release.yml`.
After validation, the workflow uses PyPI trusted publishing and publishes the container to GHCR by
digest. It generates Python and container SBOMs, records GitHub provenance and SBOM attestations,
keyless-signs the image with cosign, scans the published digest with Trivy, verifies the PyPI wheel,
image, signature, and attestations, validates/packages the supported Helm chart, then creates
GitHub release notes with the distributions, chart, and SBOMs attached. Releases require the
protected `pypi` GitHub environment and its trusted-publisher configuration; repository
contributors must not upload with long-lived PyPI tokens.

This describes the configured workflow, not a completed publication. No PyPI wheel, GHCR digest,
release SBOM, signature, or external attestation has been published from this implementation yet.

### Pre-commit Hooks

The project includes a `.pre-commit-config.yaml` for automated checks on commit:

```bash
pip install pre-commit
pre-commit install
```

### Adding a New Tool

1. Create an agent in `src/arangodb_mcp/agents/` inheriting from `ArangoAgentBase`
2. Create tool definitions in `src/arangodb_mcp/mcp_tools/` using `@mcp_app.tool`
3. Add the tool's complete classification to `src/arangodb_mcp/catalog/tools.yaml` (startup rejects unknown tools)
4. Import the new tool module in `src/arangodb_mcp/mcp_tools/__init__.py` and `src/arangodb_mcp/server.py`
5. Update the exact profile inventory contracts and add behavior tests in `tests/`

---

## Support and Governance

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes.
- Use [public GitHub Issues](https://github.com/arango-solutions/arango-solutions-mcp/issues)
  for community support and contribution coordination; scope and best-effort response targets are
  in [SUPPORT.md](SUPPORT.md).
- Report vulnerabilities only through
  [GitHub private security advisories](https://github.com/arango-solutions/arango-solutions-mcp/security/advisories/new).
- Review the [threat model](docs/threat-model.md),
  [deprecation policy](docs/deprecation-policy.md), and [security policy](SECURITY.md).

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
| **HTTP identity and authority** | Production OIDC validates discovery/JWKS, asymmetric JWT signatures, issuer, audience, expiry/not-before, operation scopes, and database allowlists. Effective authority intersects token, startup, catalog, and server-side credential policy. `MCP_AUTH_TOKEN` remains as an explicit legacy compatibility mode. |
| **AQL query budget** | `DEFAULT_AQL_MAX_RUNTIME` (default `30s`) caps every `execute-aql-query`; per-call `max_runtime` override is also accepted. |
| **AQL log redaction** | User-supplied AQL is logged as `<redacted len=N sha1=…>` by default; the sha1 prefix lets you correlate log lines for the same query without exposing literals. Set `LOG_AQL_QUERIES=true` for plaintext debugging. |
| **Secret hygiene** | Root password, `MCP_AUTH_TOKEN`, and the `password` parameter on `create-user` / `update-user` are typed as `pydantic.SecretStr`, so values are not reprinted in logs or `repr()` output. |

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
- **Self-testing** — 431 test functions across unit, framework, integration, and cluster tiers
- **Cross-platform** — runs on macOS, Linux, Windows (via Docker)

## License

See [LICENSE](LICENSE) for details.
