# SOTA MCP Competitive Scorecard

**Product:** ArangoDB MCP Server<br>
**Assessment date:** August 6, 2026<br>
**Repository baseline:** Phases 1–5 committed on the `phase1/platform-spine` branch (`fca17f4`) and pushed to origin — not yet merged to `main` or released; mechanically verified before publication<br>
**Product version:** 2.0.0 (`pyproject.toml:3`, `src/arangodb_mcp/config.py:76`)

**Revision — August 14, 2026:** The Phases 1–5 worktree this scorecard assessed was **committed**
(`fca17f4`, Aug 7) and pushed to `origin/phase1/platform-spine`, with a breaking-changes changelog
(`47aee61`, Aug 8); latest activity is Aug 8, 2026. Version remains `2.0.0`, but `CHANGELOG.md`
records **two breaking client-facing changes** (the `main.py` → `arangodb-mcp` launch entrypoint,
and the `readonly` default profile that gates the `memory` toolset), so the next release is a major
**v3.0.0**. The **82/B+** score is unchanged: the external gates it depends on — merge to `main`,
published signed PyPI/GHCR artifacts, a 30-day green operational window, and the independent MAT-003
regrade — remain unmet (no release tag exists). This revision corrects temporal/state framing only;
category scores and evidence are otherwise as of the August 6 assessment.

## Executive verdict

**Overall: 82/100 — B+**

This server is the **functional-breadth leader** in the comparison: its 81 verified tools cover
documents, graphs, AQL, search, vectors, transactions, cluster administration, backups, users,
permissions, embeddings, and shared memory (`src/arangodb_mcp/server.py:18-66`,
`tests/test_mcp_e2e.py:59-63`). No peer in this scorecard matches that native multi-model and
administrative surface.

It exceeds Neo4j's 77-point benchmark through a compact readonly default, catalog-driven policy,
parser-backed AQL safety, human confirmations, current stateless protocol behavior, MCP resources
and prompts, and blocking quality gates. Phases 4 and 5 now add local OIDC authority intersection,
request-scoped credentials, Prometheus/OpenTelemetry/audit controls, package and immutable-image
gates, a release workflow, and a supported Helm deployment. Those improvements do not justify a
self-awarded score increase. The largest remaining deficits are:

1. the legacy shared-token compatibility mode still maps to one configured database identity;
2. no PyPI wheel, GHCR digest, SBOM, signature, or provenance attestation is externally published;
3. required CI/branch-protection and interoperability evidence remains incomplete;
4. governance files are committed on the branch but not yet merged to `main` or in a public release;
5. MAT-003 still requires an independent regrade after at least 30 days of green operational,
   release, interoperability, and external-use evidence.

The defensible market position is:

> **The broadest ArangoDB-native MCP control plane, with strong locally verified identity,
> observability, package, and Helm foundations, while published distribution, independently
> observed operations, and release/adoption maturity still trail the production leaders.**

### Change since the prior baseline

- `[V]` Contributor PR [#2](https://github.com/arango-solutions/arango-solutions-mcp/pull/2)
  corrected a multi-writer data-integrity defect: `save-pattern(force=true)` now preserves the
  caller's "genuinely distinct" ruling instead of implicitly superseding a near-duplicate
  (`src/arangodb_mcp/mcp_tools/pattern_memory_tools.py:131-145`, `src/arangodb_mcp/mcp_tools/pattern_memory_tools.py:172-183`).
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
  `src/arangodb_mcp/main.py:130-144`).
- `[V]` A clean live smoke test reached healthy ArangoDB and MCP containers, returned HTTP 200 from
  `/healthz`, rejected an unauthenticated MCP request with 401, and created a vector index.
- `[V]` The latest completed local suite is green at 480 tests and 82.64% measured coverage; Ruff,
  formatting, Mypy, and the enforced 79% coverage floor also pass.
- `[V]` Dependabot covers Python, Actions, and Docker dependencies. CodeQL, exception-free
  dependency audit, full-history secret scanning, and built-image vulnerability gates are
  configured; the unused vulnerable `fastmcp` package was removed.
- `[V]` A new CI gate derives the registered tool count, test-function count, configuration
  variables, and source inventories from executable code and rejects stale README, PRD, or
  scorecard claims (`scripts/verify_docs.py:19-109`, `.github/workflows/ci.yml:43-44`).
- `[V]` A pinned ArangoDB Starter deployment was exercised locally with three agents, DBServers,
  and coordinators; the corrected cluster tier passed 4 tests with one Community-edition skip.
  The same deployment is now scheduled nightly (`tests/test_cluster.py:17-63`,
  `.github/workflows/cluster-nightly.yml:1-113`).
- `[V]` A canonical 81-tool policy catalog now drives readonly/developer/operator/admin profiles,
  graph/search additions, and fail-closed denylists (`src/arangodb_mcp/catalog/tools.yaml:1-106`,
  `src/arangodb_mcp/policy/profiles.py:10-89`).
- `[V]` The default surface is 17 readonly tools and remains below the 9,000-token contract ceiling
  (`tests/test_tool_policy.py:115-142`, `tests/test_tool_policy.py:199-207`).
- `[V]` Parser-backed AQL classification, non-disableable runtime/output/bulk/concurrency ceilings,
  and one-use bound confirmation tokens are enforced before dispatch
  (`src/arangodb_mcp/policy/aql_classifier.py:10-84`, `src/arangodb_mcp/policy/limits.py:36-160`,
  `src/arangodb_mcp/policy/confirmation.py:30-230`).
- `[V]` Resources, prompts, a versioned v3 result envelope, stateless 2026-07-28 interoperability,
  and Host/Origin controls are covered by executable contracts (`src/arangodb_mcp/mcp_content.py:22-164`,
  `src/arangodb_mcp/contracts/v3_result.py:8-100`, `tests/test_protocol_interop.py:64-139`).
- `[V]` CI now includes deterministic tool-selection, destructive-refusal, retrieval-quality, and
  latency gates. The local baseline is 90% selection, 100% refusal, MRR@10 1.0, and recall@5 1.0
  (`evals/run_quality_gates.py:40-170`, `.github/workflows/ci.yml:43-50`).
- `[V]` Phase 4 locally verifies OIDC discovery/JWKS, a signed-JWT MCP request, Prometheus scraping,
  and correlated OTLP spans (`scripts/run_phase4_integration.py:159-296`).
- `[V]` Phase 5 moves the application into the installable `arangodb_mcp` package, verifies an
  isolated wheel and immutable non-root wheel-based image, configures trusted release publication,
  and passes strict Helm/kubeconform plus live kind install/upgrade/probe/authentication
  (`pyproject.toml:10-18`, `scripts/verify_wheel.py:61-121`,
  `scripts/verify_helm.sh:13-54`, `scripts/run_helm_kind_smoke.sh:47-180`).
- `[V]` Security, contribution, ownership, support, threat-model, and deprecation documents are
  committed on the `phase1/platform-spine` branch (`SECURITY.md:1-80`, `CONTRIBUTING.md:1-51`, `.github/CODEOWNERS:1-8`,
  `SUPPORT.md:1-29`, `docs/threat-model.md:1-104`, `docs/deprecation-policy.md:1-35`).

The evidence-backed total remains **82/B+**, eleven points above the Phase 0 baseline and five
points above Neo4j's 77. Phase 4/5 implementation is recorded without changing category scores:
publishing and governance still lack their EXTERNAL gates, and MAT-003 requires an independent
post-30-day evidence review rather than a maintainer self-awarding an A.

## Method

### Evidence labels

- `[V]` Verified in source, tests, CI configuration, vendor documentation, or release metadata.
- `[I]` Reasoned inference from verified evidence.
- `[U]` Unknown from available public evidence.

The local repository received a static source audit. Competitors were assessed from public vendor
documentation, repositories, package registries, and release metadata. The latest completed suite
passed 480 tests at 82.64% measured coverage. Local live evidence includes the multi-server cluster,
Compose, Phase 4 OIDC/telemetry harness, and Phase 5 kind Helm install/upgrade harness. Published
artifact integrity, sustained production reliability, governance visibility, and adoption were not
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
| 2 | **ArangoDB MCP Server** | **19** | **14** | **13** | **14** | **8** | **9** | **5** | **82** | **B+** | High static/test / medium external |
| 3 | Bytebase DBHub | 10 | 15 | 13 | 13 | 10 | 10 | 9 | **80** | **B+** | Medium-high |
| 4 | Neo4j MCP | 10 | 14 | 13 | 13 | 9 | 9 | 9 | **77** | **B** | Medium-high |
| 5 | Qdrant MCP | 6 | 15 | 9 | 10 | 4 | 7 | 8 | **59** | **D** | Medium |
| 6 | Amazon Neptune MCP | 9 | 12 | 10 | 10 | 4 | 6 | 7 | **58** | **D** | Medium |

The best observed category scores combine to **95/100**, but they are distributed across multiple
products. ArangoDB's 13-point gap to that composite benchmark is now concentrated in identity,
operations, distribution, and ecosystem maturity rather than database or agent-safety capability.

## ArangoDB category grades

### 1. Database capability — 19/20 (A)

**Why it leads**

- `[V]` The framework contract test requires exactly 81 registered tools
  (`tests/test_mcp_e2e.py:59-63`).
- `[V]` The server covers document CRUD, database and collection management, graph management and
  traversal, AQL validation/explain/execute, indexes, vector and hybrid search, views, analyzers,
  cluster administration, transactions, backups, users, and permissions (`src/arangodb_mcp/server.py:18-61`).
- `[V]` Embedding and shared-memory tools add hybrid retrieval, provenance, reuse outcomes, and
  drift capture (`src/arangodb_mcp/server.py:63-66`, `PRD.md:263-275`).
- `[V]` Shared-memory consolidation now preserves an explicit `force=true` ruling while retaining
  default implicit and caller-selected explicit replacement behavior
  (`src/arangodb_mcp/mcp_tools/pattern_memory_tools.py:142-145`,
  `src/arangodb_mcp/mcp_tools/pattern_memory_tools.py:663-687`).
- `[V]` Dedicated graph and vector tools reduce the need to synthesize raw AQL
  (`src/arangodb_mcp/server.py:29-43`).

**Why it is not 20**

- `[V]` The pattern-memory subsystem deliberately keeps substantial business logic in the tool
  layer, a known architecture divergence (`PRD.md:275`).
- `[V]` Resources and prompts expose schema/manual/workflow context, but there is no domain-native
  progressive schema search equivalent to the strongest discovery implementations.

### 2. Agent ergonomics — 14/15 (A)

**Strengths**

- `[V]` Server instructions prescribe a manual → validate → explain → execute AQL workflow
  (`src/arangodb_mcp/server.py:11-16`).
- `[V]` The server publishes a capability map and database best practices to clients
  (`src/arangodb_mcp/server.py:18-79`).
- `[V]` Tool naming and registration are mechanically checked
  (`tests/test_mcp_e2e.py:59-67`).
- `[V]` Query budgets and dedicated traversal/search tools help keep calls bounded
  (`src/arangodb_mcp/config.py:101-105`, `src/arangodb_mcp/server.py:71-79`).
- `[V]` The default profile exposes exactly 17 readonly tools, while explicit profiles and
  graph/search toolsets expand the surface by deployment intent (`src/arangodb_mcp/policy/profiles.py:10-89`,
  `tests/test_tool_policy.py:115-142`).
- `[V]` All dispatches use one v3 success/error envelope with machine-readable limit metadata
  (`src/arangodb_mcp/contracts/v3_result.py:8-100`, `src/arangodb_mcp/policy/tool_manager.py:91-253`).
- `[V]` Manuals, schema, active profile, and status are MCP resources, with safe AQL, graph, and
  search workflow prompts (`src/arangodb_mcp/mcp_content.py:22-164`).

**Gaps**

- `[V]` The compact default still exposes 17 schemas and 8,293 estimated tokens; it does not offer
  DBHub-style dynamic two-tool discovery (`tests/test_tool_policy.py:199-207`).
- `[I]` The mandatory five-step AQL workflow improves correctness but can waste calls and tokens
  for known-safe queries.
- `[V]` The pattern-memory subsystem retains a documented business-logic exception in the tool
  layer (`PRD.md:297`).

### 3. Security and guardrails — 13/15 (A-)

**Strengths**

- `[V]` Non-loopback HTTP refuses to start without a bearer token (`src/arangodb_mcp/main.py:228-236`).
- `[V]` Token comparison is constant-time (`src/arangodb_mcp/auth_middleware.py:63`).
- `[V]` Database and MCP credentials use `SecretStr`; AQL is redacted from logs by default
  (`src/arangodb_mcp/config.py:34-40`, `src/arangodb_mcp/config.py:106-112`).
- `[V]` Server-side JavaScript transactions are disabled by default
  (`src/arangodb_mcp/config.py:96-100`).
- `[V]` `_system` deletion and primary-index deletion have explicit mechanical guards
  (`src/arangodb_mcp/mcp_tools/database_tools.py:136-137`,
  `src/arangodb_mcp/agents/index_management_agent.py:105-106`).
- `[V]` Version 3 defaults to a readonly profile; writes/admin tools require explicit enablement,
  and tool/category denylists fail closed (`src/arangodb_mcp/config.py:146-161`, `src/arangodb_mcp/policy/profiles.py:31-89`).
- `[V]` AQL policy uses the authoritative parser AST and rejects mutation or ambiguity in readonly
  mode (`src/arangodb_mcp/policy/aql_classifier.py:10-84`, `src/arangodb_mcp/agents/aql_execution_agent.py:64-91`).
- `[V]` Irreversible catalog entries require actor/action/parameter/expiry-bound one-use tokens
  minted outside MCP (`src/arangodb_mcp/policy/confirmation.py:30-230`, `scripts/mint_confirmation.py:1-57`).
- `[V]` Runtime, rows, bytes, bulk input, and concurrency have non-disableable server maxima
  (`src/arangodb_mcp/policy/limits.py:36-160`, `src/arangodb_mcp/policy/tool_manager.py:129-253`).
- `[V]` Host and Origin validation runs before authentication on HTTP transports
  (`src/arangodb_mcp/asgi/app_factory.py:20-55`, `src/arangodb_mcp/middleware/transport_security.py:11-30`).
- `[V]` Production OIDC validates discovery/JWKS, signatures, issuer, audience, time bounds, actor,
  scopes, and database claims, then intersects them with profiles, catalog policy, and
  request-scoped server-side credentials (`src/arangodb_mcp/oidc.py:39-365`,
  `src/arangodb_mcp/policy/credentials.py:21-121`,
  `src/arangodb_mcp/policy/tool_manager.py:161-170,434-471`).

**Gaps**

- `[V]` The temporary legacy bearer mode remains a shared identity backed by one configured
  ArangoDB account; production deployments must select OIDC for per-request authority.
- `[V]` The default database is `_system`, expanding the blast radius of a privileged
  configuration (`src/arangodb_mcp/config.py:37`).
- `[U]` No independent production identity-provider interoperability or sustained authorization
  telemetry has been published.

### 4. Reliability and verification — 14/15 (A)

**Strengths**

- `[V]` The repository contains 431 test functions across mock, framework-contract, integration,
  and cluster tiers; the latest parametrized suite executes 480 tests and explicitly enforces
  81-tool registration (`tests/test_mcp_e2e.py:59-74`).
- `[V]` CI runs Ruff, formatting, mypy, and Docker-backed tests on Python 3.10 and 3.11 with
  ArangoDB 3.12 (`.github/workflows/ci.yml:10-90`).
- `[V]` The force/supersede regression is tested in both directions, and PR #2's Docker-backed
  Python 3.10 and 3.11 jobs passed (`tests/test_pattern_memory_tools.py:295-325`).
- `[V]` Blocking driver work is dispatched off the event loop
  (`src/arangodb_mcp/agents/agent_base.py:100-105`, `PRD.md:305-312`).
- `[V]` Startup uses retry/backoff and a lifespan-managed connection
  (`src/arangodb_mcp/config.py:114-123`, `PRD.md:295-303`).
- `[V]` The full local suite passes 480 tests at 82.64% coverage, and CI enforces a 79% floor
  (`pyproject.toml:94-96`, `.github/workflows/ci.yml:82-97`).
- `[V]` Repository-wide Ruff check/format and the CI-equivalent Mypy command pass locally.
- `[V]` The multi-server cluster tier passes against a live three-machine starter deployment and is
  scheduled nightly with pinned container digests (`tests/test_cluster.py:17-63`,
  `.github/workflows/cluster-nightly.yml:1-113`).
- `[V]` Blocking deterministic gates cover tool selection, destructive refusal, retrieval MRR and
  recall, and latency percentiles (`evals/run_quality_gates.py:40-170`).
- `[V]` Strict/auto/legacy Streamable HTTP and SSE/stdio composition have interoperability
  contracts (`tests/test_protocol_interop.py:64-139`, `tests/test_app_factory.py:59-75`).

**Gaps**

- `[V]` First external CI runs for the new security and interoperability matrices remain pending;
  required branch checks need repository-admin configuration (`PRD.md:442-445`).
- `[V]` The deterministic latency gate is not a multi-client saturation/load benchmark.

### 5. Operations and observability — 8/15 (B-)

**Strengths**

- `[V]` HTTP deployments expose distinct `/livez` and dependency-aware `/readyz` probes; the
  deprecated `/healthz` alias retains readiness semantics (`src/arangodb_mcp/asgi/health.py:13-93`).
- `[V]` Logging supports text or field-whitelisted JSON output
  (`src/arangodb_mcp/main.py:20-60`, `src/arangodb_mcp/config.py:75-82`).
- `[V]` Startup diagnostics, AQL redaction, standardized errors, and connection retries are
  implemented (`src/arangodb_mcp/main.py:210-215`, `src/arangodb_mcp/config.py:106-123`).
- `[V]` HTTP requests receive propagated `X-Request-ID` correlation context
  (`src/arangodb_mcp/middleware/request_context.py:20-46`, `src/arangodb_mcp/asgi/app_factory.py:47-48`).
- `[V]` SLO semantics and probe failure behavior are documented and executable
  (`docs/slo.md:7-62`, `tests/test_health_endpoint.py:89-164`).
- `[V]` Dispatch enforces global per-tool concurrency ceilings
  (`src/arangodb_mcp/policy/limits.py:121-160`, `src/arangodb_mcp/policy/tool_manager.py:155-253`).
- `[V]` Prometheus metrics, OpenTelemetry request/tool/database/embedding spans, one redacted audit
  event per write/admin attempt, and per-actor/global/class/tool limits are implemented
  (`src/arangodb_mcp/observability/metrics.py:15-163`,
  `src/arangodb_mcp/observability/telemetry.py:22-75`,
  `src/arangodb_mcp/observability/audit.py:14-60`,
  `src/arangodb_mcp/policy/limits.py:176-350`).
- `[V]` The containerized Phase 4 harness observed a successful MCP metric and correlated
  request/tool/database spans (`scripts/run_phase4_integration.py:159-296`).

**Gaps**

- `[U]` No independent production telemetry window, dashboard/alert evidence, or multi-replica
  saturation benchmark has been published.
- `[V]` The initial SLO remains an objective; it has not accumulated a 30-day production window
  required for MAT-003 (`docs/slo.md:42-62`).

MongoDB is the benchmark here: public evidence shows separate health/metrics endpoints, tool
duration and count metrics, structured logging, telemetry, and agent evaluations.

### 6. Deployment and integration — 9/10 (A-)

**Strengths**

- `[V]` stdio, SSE, and Streamable HTTP are implemented (`src/arangodb_mcp/config.py:83-87`,
  `src/arangodb_mcp/main.py:177-180`, `src/arangodb_mcp/main.py:220-246`).
- `[V]` Dockerfile and Docker Compose deployment paths are included (`README.md:138-184`).
- `[V]` The server fails closed if configured auth cannot be wrapped around the FastMCP ASGI app
  (`src/arangodb_mcp/main.py:160-169`).
- `[V]` Compose requires `MCP_AUTH_TOKEN`, enables ArangoDB vector indexing, supports configurable
  host ports, and waits for an authenticated ArangoDB health probe
  (`docker-compose.yml:4-39`).
- `[V]` The MCP image has a database-backed health check, and standalone HTTP startup explicitly
  owns the ArangoDB connector lifecycle (`Dockerfile:25-26`, `src/arangodb_mcp/main.py:130-144`).
- `[V]` Static deployment contracts and a clean live Compose smoke test verify the documented
  secret, health, and vector behavior (`tests/test_deployment_contract.py:12-38`).
- `[V]` The runtime image is a multi-stage Alpine build running as an unprivileged user
  (`Dockerfile:1-52`, `tests/test_deployment_contract.py:65-82`).
- `[V]` Streamable HTTP defaults to stateless JSON responses with strict/legacy/auto compatibility,
  2026-07-28 routing metadata, cache hints, and Host/Origin checks (`src/arangodb_mcp/server.py:88-106`,
  `src/arangodb_mcp/middleware/protocol.py:24-236`).
- `[V]` The `src/` package declares the `arangodb-mcp` console entry point and packaged catalog and
  manuals; an isolated wheel-only install verifies imports, data, tools, prompts/resources, and CLI
  (`pyproject.toml:10-18`, `scripts/verify_wheel.py:61-121`).
- `[V]` The runtime image installs the wheel, removes package installers, makes the environment
  read-only, and runs as a non-root user (`Dockerfile:12-29,46-51`).
- `[V]` The supported Helm chart documents secrets, probes, resources, hardening, digest pinning,
  and upgrades; strict lint/kubeconform and live kind install/upgrade/probe/authentication pass
  locally (`deploy/helm/arangodb-mcp/README.md:1-113`,
  `scripts/verify_helm.sh:13-54`, `scripts/run_helm_kind_smoke.sh:47-180`).

**Gaps**

- `[U]` No PyPI package or GHCR digest is externally published, so install/start from published
  immutable artifacts remains unverified.
- `[V]` The chart deploys only the MCP server; operators still provide ArangoDB, ingress/TLS,
  external secrets, network policy, and multi-cluster operations.

### 7. Ecosystem and release maturity — 5/10 (D)

**Strengths**

- `[V]` Apache-2.0 licensing and a repeatable CI workflow are present (`LICENSE:1`,
  `.github/workflows/ci.yml:1-90`).
- `[V]` The repository has current implementation activity through August 8, 2026.
- `[V]` A non-owner collaborator submitted a focused correctness fix that was reviewed and merged
  through PR [#2](https://github.com/arango-solutions/arango-solutions-mcp/pull/2).
- `[V]` Dependabot covers Python, GitHub Actions, and Docker; CodeQL and pip-audit workflows run on
  pull requests, `main`, and a weekly schedule (`.github/dependabot.yml:1-24`,
  `.github/workflows/security.yml:1-84`).
- `[V]` The release workflow configures PyPI trusted publishing, GHCR digest publication, Python and
  container SBOM/provenance attestations, keyless cosign signing, digest scanning, verification,
  Helm packaging, and GitHub release creation (`.github/workflows/release.yml:113-347`).
- `[V]` Local governance files define private vulnerability reporting, contribution flow,
  ownership, support targets, threat boundaries, and deprecation/upgrade policy
  (`SECURITY.md:1-80`, `CONTRIBUTING.md:1-51`, `.github/CODEOWNERS:1-8`,
  `SUPPORT.md:1-29`, `docs/threat-model.md:1-104`, `docs/deprecation-policy.md:1-35`).

**Gaps**

- `[U]` No release execution proves trusted publication, SBOMs, signatures, provenance, or
  verification against externally published artifacts.
- `[U]` Governance files are committed and pushed on the `phase1/platform-spine` branch but are not
  yet on `main` or in a release, so they cannot yet be credited as public response/contribution paths.
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

ArangoDB now leads 82 to 77 through much greater multi-model/administrative breadth, a compact
readonly default, parser-backed query policy, irreversible-action confirmation, resources/prompts,
and deterministic quality gates. Neo4j retains the simpler four-tool graph surface, mature package
distribution, and per-request remote credentials, so it remains the principal **graph simplicity
and request-identity benchmark**.

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
| Closed | Compact discovery and tool profiles | DBHub: 2 default tools; Qdrant: 2 tools | 17-tool readonly default plus explicit profiles/toolsets (`src/arangodb_mcp/policy/profiles.py:10-89`) | Credited |
| Closed | Read-only, denylist, query policy, and confirmation | MongoDB/DBHub/Neo4j provide mechanical restrictions | Catalog policy, parser classification, hard limits, and one-use confirmation (`src/arangodb_mcp/policy/tool_manager.py:38-253`) | Credited |
| Closed | MCP 2026-07-28 interoperability | DBHub documents current stateless compatibility | Strict/auto/legacy stateless contracts and live probe (`tests/test_protocol_interop.py:64-139`) | Credited |
| Closed locally | OAuth/per-request identity and scopes | Neo4j uses per-request DB identity; Toolbox sets broader SOTA | OIDC authority intersection and request credentials implemented; independent production evidence pending (`src/arangodb_mcp/policy/tool_manager.py:434-471`) | Regrade pending |
| Closed locally | Metrics, traces, and audit events | MongoDB exposes Prometheus; DBHub exposes request traces | Prometheus, OTLP, audit, and limit telemetry implemented and locally exercised (`scripts/run_phase4_integration.py:159-296`) | Regrade pending |
| P1 | Release automation and provenance | MongoDB, Neo4j, DBHub publish packages/images/releases | Workflow implemented; no published artifacts or attestations (`.github/workflows/release.yml:113-347`) | +4 |
| P1 | External verification enforcement | MongoDB has published accuracy/evaluation and security pipelines | Local gates pass; first external security/interop runs and branch protection remain open | +1 |
| Closed | Resources/prompts and schema-first discovery | Neptune exposes resources; peers have compact discovery | Four resource capabilities and three guided prompts (`src/arangodb_mcp/mcp_content.py:22-164`) | Credited |
| P2 | Adoption and governance | Competitors have releases, users, and contribution paths | Governance exists locally but is not public; 30-day adoption gate remains open | +2 |

Phases 1–3 added **+11** after re-audit. Phase 4/5 improvements await the independent post-30-day
MAT-003 review. Remaining score impacts are directional estimates and are not additive without that
evidence-backed regrade.

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

1. **Completed:** readonly/developer/operator/admin profiles and graph/search toolsets.
2. **Completed:** compact 17-tool readonly default with a bounded schema footprint.
3. **Completed:** parser-backed AQL classification and hard runtime/row/byte/bulk/concurrency
   ceilings.
4. **Completed:** actor/action/parameter/expiry-bound one-use confirmation for irreversible tools.
5. **Completed:** one structured v3 success/error envelope with dated legacy compatibility.

### Phase 2 — Meet the production MCP bar

1. **Completed locally:** stateless MCP 2026-07-28 routing, cache, Host/Origin, and compatibility.
2. **Completed locally:** OAuth 2.1/OIDC resource-server validation, protected-resource metadata,
   per-request identity, scopes, database policy, and request-scoped credentials.
3. **Completed locally:** OpenTelemetry traces and Prometheus metrics for tool, AQL, dependency,
   and limiter behavior.
4. **Completed locally:** one structured, redacted audit event for every mutation/privileged
   attempt.

### Phase 3 — Prove and distribute quality

1. **Workflow implemented; publication pending:** publish versioned Python and container artifacts
   with signed provenance, SBOMs, changelogs, and automated vulnerability scans.
2. **Completed for the deterministic baseline:** MCP interoperability, tool selection,
   destructive refusal, retrieval MRR/recall, latency, and output ceilings are blocking gates.
3. Publish reproducible latency/concurrency benchmarks and the locally implemented governance
   policies.
4. **Completed locally:** supported Helm chart with static validation and live kind
   install/upgrade/probe/authentication acceptance.

## What would move this server to A-range

The current **82/B+** result needs eight additional points for A-range. The shortest credible path
is to preserve the 19/20 capability and 14/15 ergonomics scores while:

- raising security from 13 to 15 with OIDC scopes, authority intersection, and request-scoped
  least-privilege credentials;
- raising operations from 8 to at least 12 with metrics, traces, complete audit events, propagated
  correlation, and per-actor load controls;
- raising deployment and maturity from 14 combined to at least 16 through published signed
  artifacts, Helm, governance, and independently observable use.

Phase 4/5 implementation may support a future **90–92/A** result, but the score remains **82/B+**
until external interoperability, security, release, operational, governance, and use evidence
passes and an independent MAT-003 regrade occurs after at least 30 days.

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
- `[V]` Latest completed local coverage is 82.64%; production throughput, failure rate, and adoption remain
  unverified.
- `[U]` The first external CI runs for the new security and interoperability implementation had
  not been captured when this regrade was finalized.
- Scores should be recalculated after material protocol, security, release, or tool-surface
  changes.
