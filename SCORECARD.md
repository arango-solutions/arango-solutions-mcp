# SOTA MCP Competitive Scorecard

**Product:** ArangoDB MCP Server<br>
**Assessment date:** August 5, 2026<br>
**Repository baseline:** Phase 0 implementation on `main` at `8eb5d40`<br>
**Product version:** 2.0.0 (`pyproject.toml:3`, `config.py:76`)

## Executive verdict

**Overall: 71/100 — B-**

This server is the **functional-breadth leader** in the comparison: its 81 verified tools cover
documents, graphs, AQL, search, vectors, transactions, cluster administration, backups, users,
permissions, embeddings, and shared memory (`server.py:18-66`,
`tests/test_mcp_e2e.py:59-63`). No peer in this scorecard matches that native multi-model and
administrative surface.

It is **not yet SOTA as a production MCP service**. MongoDB leads on operations, evaluation, and
release engineering; DBHub leads on progressive disclosure and token efficiency; Neo4j leads on
compact graph ergonomics and per-request remote identity. This server's largest deficits are:

1. no progressive tool discovery or deploy-time tool profiles;
2. no read-only mode, confirmation framework, or query-class enforcement;
3. one shared MCP bearer token maps to one broadly privileged database identity;
4. no Prometheus/OpenTelemetry instrumentation or unified audit trail;
5. no automated package/container release or provenance;
6. incomplete compatibility with the stateless MCP 2026-07-28 bar.

The defensible market position is:

> **The broadest ArangoDB-native MCP control plane, with above-average code-level safety and test
> depth, but behind the strongest competitors in agent ergonomics, least privilege, observability,
> protocol currency, and release maturity.**

### Change since the prior baseline

- `[V]` Contributor PR [#2](https://github.com/arango-solutions/arango-solutions-mcp/pull/2)
  corrected a multi-writer data-integrity defect: `save-pattern(force=true)` now preserves the
  caller's "genuinely distinct" ruling instead of implicitly superseding a near-duplicate
  (`mcp_tools/pattern_memory_tools.py:131-145`, `mcp_tools/pattern_memory_tools.py:172-183`).
- `[V]` Two regression tests pin both sides of the invariant: forced saves do not supersede, while
  ordinary near-duplicates still do (`tests/test_pattern_memory_tools.py:295-325`).
- `[V]` PRD item P-2 now distinguishes implicit superseding from explicit replacement
  (`PRD.md:270`).
- `[V]` At the prior `a49d9b7` baseline, the two Docker-backed CI test jobs passed on Python 3.10
  and 3.11, but the lint job failed on a pre-existing Ruff import-order violation
  ([CI run](https://github.com/arango-solutions/arango-solutions-mcp/actions/runs/31053199522)).
- `[V]` Phase 0 established 44 stable, owned, evidence-gated v3 requirements in the PRD and
  replaced the blanket implementation claim with requirement-level states (`PRD.md:39-55`,
  `PRD.md:367-473`).
- `[V]` The Compose path now requires independent MCP/database secrets, enables vector indexes,
  provides working dependency and container health checks, and initializes the database connector
  for HTTP service startup (`docker-compose.yml:1-40`, `Dockerfile:20-28`,
  `main.py:130-144`).
- `[V]` A clean live smoke test reached healthy ArangoDB and MCP containers, returned HTTP 200 from
  `/healthz`, rejected an unauthenticated MCP request with 401, and created a vector index.
- `[V]` The Phase 0 quality baseline is locally green: Ruff check/format, the CI-equivalent Mypy
  command, and all 392 non-cluster tests pass; coverage is measured at 79.16% and fails below 79%.
- `[V]` Dependabot now covers Python, Actions, and Docker dependencies; CodeQL and dependency audit
  workflows are present. Compatible dependencies were upgraded, leaving only six explicitly
  time-bounded FastMCP 0.2 exceptions pending the SDK migration.
- `[V]` A new CI gate derives the registered tool count, test-function count, configuration
  variables, and source inventories from executable code and rejects stale README, PRD, or
  scorecard claims (`scripts/verify_docs.py:19-109`, `.github/workflows/ci.yml:43-44`).
- `[V]` A pinned ArangoDB Starter deployment was exercised locally with three agents, DBServers,
  and coordinators; the corrected cluster tier passed 4 tests with one Community-edition skip.
  The same deployment is now scheduled nightly (`tests/test_cluster.py:17-63`,
  `.github/workflows/cluster-nightly.yml:1-113`).

The total is now **71/B-**. The secure, vector-capable Compose path closes two deployment points;
enforced coverage and a locally green quality baseline restore one reliability point; dependency
automation and security scanning add one maturity point; live nightly cluster verification adds one
reliability point. Mechanical documentation checks close the remaining Phase 0 consistency gap
without changing a weighted category score. The implementation is published at `8eb5d40`; GitHub
Actions had not registered runs for that commit when this scorecard was finalized.

## Method

### Evidence labels

- `[V]` Verified in source, tests, CI configuration, vendor documentation, or release metadata.
- `[I]` Reasoned inference from verified evidence.
- `[U]` Unknown from available public evidence.

The local repository received a static source audit. Competitors were assessed from public
vendor documentation, repositories, package registries, and release metadata. For this update,
the full 392-test non-cluster suite and the live multi-server cluster tier passed locally, a clean
Compose deployment was exercised live,
and GitHub CI status was inspected.
The full local suite, live coverage percentage, latency, and production reliability were not
independently measured.

### Weighted rubric

| Category | Weight | SOTA bar |
|---|---:|---|
| Database capability | 20 | Broad, composable data operations with domain-native discovery and analysis |
| Agent ergonomics | 15 | Small default surface, progressive disclosure, bounded output, consistent schemas |
| Security and guardrails | 15 | Read-only profiles, scoped identity, query classification, confirmations, safe HTTP |
| Reliability and verification | 15 | Unit/integration/E2E tests, enforced coverage, live-engine and agent-quality gates |
| Operations and observability | 15 | Health, metrics, traces, structured logs, auditability, resilience |
| Deployment and integration | 10 | Current transports, easy install, container/package distribution, cloud readiness |
| Ecosystem and release maturity | 10 | Active releases, provenance, security automation, adoption, governance |
| **Total** | **100** | A composite target; no compared product demonstrates every item |

Grades: **A** 90–100, **A-** 85–89, **B+** 80–84, **B** 75–79, **B-** 70–74,
**C+** 65–69, **C** 60–64, **D** below 60.

This is a competitive-position score, not a universal product-quality ranking. Focused products
such as Qdrant intentionally trade breadth for simplicity.

## Competitive ranking

| Rank | Server | Capability /20 | Ergonomics /15 | Security /15 | Reliability /15 | Operations /15 | Deployment /10 | Maturity /10 | Total | Grade | Evidence confidence |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | MongoDB MCP | 18 | 11 | 12 | 14 | 14 | 9 | 10 | **88** | **A-** | Medium-high |
| 2 | Bytebase DBHub | 10 | 15 | 13 | 13 | 10 | 10 | 9 | **80** | **B+** | Medium-high |
| 3 | Neo4j MCP | 10 | 14 | 13 | 13 | 9 | 9 | 9 | **77** | **B** | Medium-high |
| 4 | **ArangoDB MCP Server** | **19** | **10** | **9** | **13** | **7** | **8** | **5** | **71** | **B-** | High static / medium deployment |
| 5 | Qdrant MCP | 6 | 15 | 9 | 10 | 4 | 7 | 8 | **59** | **D** | Medium |
| 6 | Amazon Neptune MCP | 9 | 12 | 10 | 10 | 4 | 6 | 7 | **58** | **D** | Medium |

The best observed category scores combine to **95/100**, but they are distributed across multiple
products. ArangoDB's 25-point gap to that composite benchmark is mainly operational and
productization debt, not missing database functionality.

## ArangoDB category grades

### 1. Database capability — 19/20 (A)

**Why it leads**

- `[V]` The framework contract test requires exactly 81 registered tools
  (`tests/test_mcp_e2e.py:59-63`).
- `[V]` The server covers document CRUD, database and collection management, graph management and
  traversal, AQL validation/explain/execute, indexes, vector and hybrid search, views, analyzers,
  cluster administration, transactions, backups, users, and permissions (`server.py:18-61`).
- `[V]` Embedding and shared-memory tools add hybrid retrieval, provenance, reuse outcomes, and
  drift capture (`server.py:63-66`, `PRD.md:263-275`).
- `[V]` Shared-memory consolidation now preserves an explicit `force=true` ruling while retaining
  default implicit and caller-selected explicit replacement behavior
  (`mcp_tools/pattern_memory_tools.py:142-145`,
  `mcp_tools/pattern_memory_tools.py:663-687`).
- `[V]` Dedicated graph and vector tools reduce the need to synthesize raw AQL
  (`server.py:29-43`).

**Why it is not 20**

- `[V]` No MCP resources or prompts are registered; schema and manuals are exposed only as tools.
- `[V]` The pattern-memory subsystem deliberately keeps substantial business logic in the tool
  layer, a known architecture divergence (`PRD.md:275`).
- `[V]` Retrieval-quality evaluation is required by the PRD but the cited harness lives outside
  this repository and is not part of its CI (`PRD.md:341-346`).

### 2. Agent ergonomics — 10/15 (B-)

**Strengths**

- `[V]` Server instructions prescribe a manual → validate → explain → execute AQL workflow
  (`server.py:11-16`).
- `[V]` The server publishes a capability map and database best practices to clients
  (`server.py:18-79`).
- `[V]` Tool naming and registration are mechanically checked
  (`tests/test_mcp_e2e.py:59-67`).
- `[V]` Query budgets and dedicated traversal/search tools help keep calls bounded
  (`config.py:101-105`, `server.py:71-79`).

**Gaps**

- `[V]` All 81 tools are exposed together; there is no DBHub-style progressive discovery,
  category loading, or read-only/admin profile.
- `[I]` The mandatory five-step AQL workflow improves correctness but can waste calls and tokens
  for known-safe queries.
- `[V]` Core agent tools and newer pattern/embedding tools use different response envelope shapes,
  increasing client parsing ambiguity (`mcp_tools/_support.py:33-59`,
  `PRD.md:275`).
- `[V]` Successful AQL responses echo the complete query, which can add unnecessary context
  (`agents/aql_execution_agent.py:72-74`).

### 3. Security and guardrails — 9/15 (C)

**Strengths**

- `[V]` Non-loopback HTTP refuses to start without a bearer token (`main.py:228-236`).
- `[V]` Token comparison is constant-time (`auth_middleware.py:63`).
- `[V]` Database and MCP credentials use `SecretStr`; AQL is redacted from logs by default
  (`config.py:34-40`, `config.py:106-112`).
- `[V]` Server-side JavaScript transactions are disabled by default
  (`config.py:96-100`).
- `[V]` `_system` deletion and primary-index deletion have explicit mechanical guards
  (`mcp_tools/database_tools.py:136-137`,
  `agents/index_management_agent.py:105-106`).

**Gaps**

- `[V]` A valid MCP bearer token receives the authority of one configured ArangoDB account; there
  are no per-request identities, MCP scopes, or per-tool authorization (`PRD.md:625-630`).
- `[V]` The default database is `_system`, expanding the blast radius of a privileged
  configuration (`config.py:37`).
- `[V]` `execute-aql-query` permits arbitrary AQL without read/write classification
  (`agents/aql_execution_agent.py:69`).
- `[V]` There is no server-wide read-only mode, tool/category denylist, or deployment profile.
- `[V]` Most destructive tools lack a mechanical confirmation token; hot-backup restore/delete
  and collection deletion are one-call operations
  (`agents/backup_management_agent.py:83-89`,
  `mcp_tools/collection_tools.py:212-236`).
- `[V]` The per-call AQL budget can be disabled with `max_runtime=0`
  (`mcp_tools/aql_tools.py:56-60`).

### 4. Reliability and verification — 13/15 (A-)

**Strengths**

- `[V]` The repository contains 355 test functions across mock, framework-contract, integration,
  and cluster tiers; 81-tool registration is explicitly enforced
  (`tests/test_mcp_e2e.py:59-74`, `PRD.md:503-552`).
- `[V]` CI runs Ruff, formatting, mypy, and Docker-backed tests on Python 3.10 and 3.11 with
  ArangoDB 3.12 (`.github/workflows/ci.yml:10-90`).
- `[V]` The force/supersede regression is tested in both directions, and PR #2's Docker-backed
  Python 3.10 and 3.11 jobs passed (`tests/test_pattern_memory_tools.py:295-325`).
- `[V]` Blocking driver work is dispatched off the event loop
  (`agents/agent_base.py:100-105`, `PRD.md:305-312`).
- `[V]` Startup uses retry/backoff and a lifespan-managed connection
  (`config.py:114-123`, `PRD.md:295-303`).
- `[V]` The full 392-test non-cluster suite passes locally at 79.16% coverage, and CI now enforces
  a 79% floor (`pyproject.toml:76-78`, `.github/workflows/ci.yml:82-94`).
- `[V]` Repository-wide Ruff check/format and the CI-equivalent Mypy command pass locally.
- `[V]` The multi-server cluster tier passes against a live three-machine starter deployment and is
  scheduled nightly with pinned container digests (`tests/test_cluster.py:17-63`,
  `.github/workflows/cluster-nightly.yml:1-113`).

**Gaps**

- `[V]` No load, concurrency, MCP interoperability, or in-repository retrieval-quality gate is
  present.
- `[V]` Type checking disables several material error classes in CI
  (`.github/workflows/ci.yml:43-44`).
- `[V]` Published `main` is still red at the assessed commit; the green worktree baseline has not
  yet been independently verified by GitHub CI
  ([CI run](https://github.com/arango-solutions/arango-solutions-mcp/actions/runs/31053199522)).

### 5. Operations and observability — 7/15 (C+)

**Strengths**

- `[V]` HTTP deployments expose a database-backed `/healthz` endpoint
  (`main.py:74-115`).
- `[V]` Logging supports text or field-whitelisted JSON output
  (`main.py:20-60`, `config.py:75-82`).
- `[V]` Startup diagnostics, AQL redaction, standardized errors, and connection retries are
  implemented (`main.py:210-215`, `config.py:106-123`).

**Gaps**

- `[V]` Prometheus metrics and OpenTelemetry are explicitly not implemented
  (`PRD.md:625-630`).
- `[V]` There are no request IDs, tool latency/error counters, distributed traces, or unified
  audit records for database mutations.
- `[V]` Neither the Dockerfile nor MCP Compose service defines a container health check.
- `[V]` There is no runtime concurrency limit, circuit breaker, or documented SLO.

MongoDB is the benchmark here: public evidence shows separate health/metrics endpoints, tool
duration and count metrics, structured logging, telemetry, and agent evaluations.

### 6. Deployment and integration — 8/10 (B+)

**Strengths**

- `[V]` stdio, SSE, and Streamable HTTP are implemented (`config.py:83-87`,
  `main.py:177-180`, `main.py:220-246`).
- `[V]` Dockerfile and Docker Compose deployment paths are included (`README.md:138-184`).
- `[V]` The server fails closed if configured auth cannot be wrapped around the FastMCP ASGI app
  (`main.py:160-169`).
- `[V]` Compose requires `MCP_AUTH_TOKEN`, enables ArangoDB vector indexing, supports configurable
  host ports, and waits for an authenticated ArangoDB health probe
  (`docker-compose.yml:4-39`).
- `[V]` The MCP image has a database-backed health check, and standalone HTTP startup explicitly
  owns the ArangoDB connector lifecycle (`Dockerfile:25-26`, `main.py:130-144`).
- `[V]` Static deployment contracts and a clean live Compose smoke test verify the documented
  secret, health, and vector behavior (`tests/test_deployment_contract.py:12-38`).

**Gaps**

- `[V]` The project is not built as a distributable Python package (`pyproject.toml:7`) and has no
  repository release or container-publishing workflow.
- `[V]` No Kubernetes, Helm, cloud deployment, or multi-instance guidance is provided.
- `[I]` The current SDK stack predates the stateless MCP 2026-07-28 architecture; explicit support
  for required method/name headers, origin validation, stateless operation, and current
  authorization discovery is not demonstrated.

### 7. Ecosystem and release maturity — 5/10 (D)

**Strengths**

- `[V]` Apache-2.0 licensing and a repeatable CI workflow are present (`LICENSE:1`,
  `.github/workflows/ci.yml:1-90`).
- `[V]` The repository has current implementation activity through August 5, 2026.
- `[V]` A non-owner collaborator submitted a focused correctness fix that was reviewed and merged
  through PR [#2](https://github.com/arango-solutions/arango-solutions-mcp/pull/2).
- `[V]` Dependabot covers Python, GitHub Actions, and Docker; CodeQL and pip-audit workflows run on
  pull requests, `main`, and a weekly schedule (`.github/dependabot.yml:1-24`,
  `.github/workflows/security.yml:1-84`).

**Gaps**

- `[V]` There are no git tags, GitHub release workflow, PyPI publication, automated container
  publication, changelog, or artifact provenance in this repository.
- `[V]` No SBOM, image scan, secret scan, signed provenance, or artifact verification is configured.
- `[V]` Six FastMCP 0.2 advisories are temporarily excepted until October 1, 2026; removal requires
  the planned breaking SDK migration (`.github/workflows/security.yml:62-84`).
- `[V]` No `SECURITY.md`, `CONTRIBUTING.md`, or public support policy is present.
- `[V]` Public adoption evidence remains limited to an initial collaborator contribution, while
  the compared peers have measurable stars, downloads, releases, or vendor distribution.
- `[V]` Tool/test inventories, configuration variables, and immutable release-history references
  are now checked mechanically in CI (`scripts/verify_docs.py:19-109`,
  `.github/workflows/ci.yml:43-44`).

## Head-to-head assessment

### Versus MongoDB MCP

ArangoDB wins on unified graph + document + search/vector + cluster/backup coverage. MongoDB wins
decisively on managed-platform integration, configurable tool restrictions, confirmations,
metrics, agent evaluations, security automation, distribution, and release provenance. MongoDB
is the principal **production-readiness benchmark**.

### Versus Bytebase DBHub

ArangoDB provides far more administration, graph, and vector functionality. DBHub's two-tool
default, progressive schema search, stateless MCP 2026-07-28 support, read-only enforcement,
static-token HTTP controls, traces, and one-command distribution make it the principal
**agent-ergonomics benchmark**.

### Versus Neo4j MCP

ArangoDB has much greater database and operational breadth. Neo4j's four-tool graph surface,
schema introspection, read/write Cypher split, query classification, and per-request HTTP
credentials make it the principal **graph security and simplicity benchmark**.

### Versus Amazon Neptune MCP

ArangoDB wins on transports, breadth, local deployment, graph operations, and code-level
guardrails. Neptune's AWS credential chain, IAM, and VPC integration are stronger for AWS-native
identity and network controls. Neptune is the **cloud identity benchmark**, not the feature
leader.

### Versus Qdrant MCP

ArangoDB includes a substantially broader vector, hybrid-search, database, graph, and memory
surface. Qdrant's two-tool interface and read-only mode are easier for an agent to reason about.
Qdrant is the **focused semantic-memory ergonomics benchmark**.

## SOTA gap register

| Priority | Gap | Competitive evidence | Current evidence | Score impact |
|---:|---|---|---|---:|
| P0 | Progressive disclosure and tool profiles | DBHub: 2 default tools; Qdrant: 2 tools | 81 always registered (`tests/test_mcp_e2e.py:59-63`) | +4 |
| P0 | Read-only, denylist, and confirmation framework | MongoDB/DBHub/Neo4j provide mechanical restrictions | No global mode; arbitrary AQL (`agents/aql_execution_agent.py:69`) | +5 |
| P0 | MCP 2026-07-28 interoperability | DBHub documents current stateless compatibility | Current support not demonstrated | +3 |
| P1 | OAuth/per-request identity and scopes | Neo4j uses per-request DB identity; Toolbox sets broader SOTA | One static token → one DB identity (`PRD.md:625-630`) | +4 |
| P1 | Metrics, traces, and audit events | MongoDB exposes Prometheus; DBHub exposes request traces | Logs + health only (`PRD.md:625-630`) | +5 |
| P1 | Release automation and provenance | MongoDB, Neo4j, DBHub publish packages/images/releases | No tags or publish workflows | +4 |
| P1 | Verification enforcement | MongoDB has accuracy/evaluation and security pipelines | Published `main` is not yet green; cluster CI excluded | +2 |
| P2 | Resources/prompts and schema-first discovery | Neptune exposes resources; peers have compact discovery | Tool-only discovery | +2 |
| P2 | Adoption and governance | Competitors have releases, users, and contribution paths | No support/security/contribution policy | +2 |

Closed in Phase 0: the secure, vector-capable default deployment path added **+2**; quality,
security-automation, nightly-cluster, and documentation gates added **+3**. Remaining score impacts
are directional estimates and are not additive without re-audit.

## Recommended roadmap

### Phase 0 — Repair credibility and defaults

1. **Completed:** Docker Compose starts with explicit secret injection, vector indexing, and
   database-backed health checks.
2. **Completed:** Reconciled tool/test counts, architecture inventories, configuration variables,
   and release-history claims; CI now rejects documentation drift.
3. **Completed:** lint/format/type-check are green locally; coverage enforcement, Dependabot,
   CodeQL, dependency audit, and a real pinned nightly cluster tier are configured and locally
   verified.

### Phase 1 — Make breadth safe and usable

1. Add deployment profiles such as `readonly`, `developer`, `graph`, `search`, and `admin`.
2. Add progressive tool discovery or category loading so clients do not ingest 81 schemas by
   default.
3. Classify AQL as read/write/admin before execution; enforce row, byte, and runtime ceilings.
4. Require confirmation tokens for irreversible collection, database, backup, cluster, user, and
   permission operations.
5. Standardize every tool on one structured success/error envelope.

### Phase 2 — Meet the production MCP bar

1. Upgrade and test against MCP 2026-07-28, including stateless HTTP behavior, required headers,
   origin checks, backwards compatibility, and formal authorization discovery.
2. Replace the shared HTTP secret model with OAuth 2.1/OIDC resource-server support, per-request
   identity, scopes, and database/tool authorization.
3. Add OpenTelemetry traces and Prometheus metrics for tool counts, latency, errors, AQL runtime,
   pool pressure, and dependency calls.
4. Emit a structured, redacted audit event for every mutation and privileged action.

### Phase 3 — Prove and distribute quality

1. Publish versioned Python and container artifacts with signed provenance, SBOMs, changelogs, and
   automated vulnerability scans.
2. Add MCP interoperability tests plus agent evaluations for tool-selection accuracy, task
   completion, token cost, output size, and destructive-action refusal.
3. Publish reproducible latency/concurrency benchmarks and an explicit support/security policy.

## What would move this server to A-range

An A-range result requires more than additional tools. The shortest credible path is:

- preserve the 19/20 capability lead;
- raise ergonomics from 10 to at least 13 through progressive disclosure and consistent schemas;
- raise security from 9 to at least 13 through profiles, classification, confirmation, and scoped
  identity;
- raise operations from 7 to at least 12 through metrics, traces, audit events, and load controls;
- raise deployment/maturity from 9 combined to at least 17 through current MCP support and
  automated, provenanced releases.

That moves the product from **66/C+** to approximately **85–90/A-**, assuming the changes are
verified by live interoperability, security, and agent-quality gates.

## Competitor evidence

### Neo4j MCP

- Official project, 278 GitHub stars, stable v1.5.3 released June 11, 2026.
- Four tools: schema, read/write Cypher, and GDS procedure discovery.
- stdio and stateless HTTP; per-request Basic/Bearer auth; mature package and release channels.
- Sources: [repository](https://github.com/neo4j/mcp),
  [documentation](https://neo4j.com/docs/mcp/current/),
  [authentication](https://neo4j.com/docs/mcp/current/authentication/),
  [releases](https://github.com/neo4j/mcp/releases).

### MongoDB MCP

- Official project, 1,091 GitHub stars; v2.0.0 released August 4, 2026.
- Broad database and Atlas surface with read-only/tool-category controls, limits, metrics, and
  extensive evaluations.
- Sources: [repository](https://github.com/mongodb-js/mongodb-mcp-server),
  [documentation](https://www.mongodb.com/docs/mcp-server/),
  [releases](https://github.com/mongodb-js/mongodb-mcp-server/releases),
  [Docker image](https://hub.docker.com/r/mongodb/mongodb-mcp-server).

### Amazon Neptune MCP

- AWS Labs-maintained; PyPI package 1.0.20.
- Four tools plus status/schema resources; stdio; IAM/AWS credential chain.
- Sources: [repository](https://github.com/awslabs/mcp/tree/main/src/amazon-neptune-mcp-server),
  [documentation](https://awslabs.github.io/mcp/servers/amazon-neptune-mcp-server),
  [PyPI](https://pypi.org/project/awslabs.amazon-neptune-mcp-server/).

### Qdrant MCP

- Official project, 1,488 GitHub stars; v0.8.1 released December 10, 2025.
- Two focused store/find tools; stdio, SSE, and Streamable HTTP; Qdrant API key and read-only mode.
- Sources: [repository](https://github.com/qdrant/mcp-server-qdrant),
  [release](https://github.com/qdrant/mcp-server-qdrant/releases/tag/v0.8.1),
  [PyPI](https://pypi.org/project/mcp-server-qdrant/).

### Bytebase DBHub

- Bytebase-backed, 3,289 GitHub stars and approximately 41,769 weekly npm downloads; v1.2.0
  released July 31, 2026.
- Two-tool default, current stateless HTTP, read-only enforcement, request traces, and broad
  package/container distribution.
- Sources: [repository](https://github.com/bytebase/dbhub),
  [documentation](https://dbhub.ai/),
  [transport and auth](https://dbhub.ai/config/command-line),
  [releases](https://github.com/bytebase/dbhub/releases).

### SOTA protocol reference

- MCP 2026-07-28 establishes the current stateless core, required Streamable HTTP routing headers,
  MRTR interactions, an extensions framework, and authorization hardening.
- Sources: [release overview](https://blog.modelcontextprotocol.io/posts/2026-07-28/),
  [Streamable HTTP specification](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http).

## Evidence limitations

- Competitor features were not installed or independently penetration-tested.
- Public stars/downloads indicate adoption, not production quality.
- No peer publishes directly comparable production usage, support SLA, independent security
  audit, standardized interoperability result, or latency/token benchmark.
- `[U]` The local server's live coverage, throughput, failure rate, and production adoption remain
  unverified; current CI status is verified red.
- Scores should be recalculated after material protocol, security, release, or tool-surface
  changes.
