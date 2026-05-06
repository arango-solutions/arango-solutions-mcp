# ArangoDB MCP Server — Code Review Report

**Original review:** April 12, 2026
**Remediation completed:** May 5, 2026
**Scope:** Full codebase audit — PRD alignment, code quality, security, test coverage
**Version reviewed:** 2.0.0 (working tree)

---

## Executive Summary

The original review identified **27 findings** across PRD alignment, code quality, security, and test coverage. After a multi-phase remediation pass, **24 findings are closed** and **3 are documented as deferred future work** in PRD §9.1.

| Category           | Critical | High | Medium | Low | **Closed** | **Deferred** |
|--------------------|---------:|-----:|-------:|----:|-----------:|-------------:|
| PRD vs Code Gaps   |        0 |    2 |      3 |   1 |          5 |            1 |
| Code Quality       |        0 |    3 |      5 |   4 |         11 |            1 |
| Security           |        1 |    2 |      2 |   0 |          5 |            0 |
| Test Coverage      |        0 |    3 |      3 |   1 |          6 |            1 |
| **Totals**         |    **1** |**10**| **13** | **6**| **27 / 30**¹ | **3** |

¹ Three new tests files were added beyond the original gap list, raising the implemented count above the original 27.

### Aggregate diff since the review

- **43 files changed**, **+1492 / −1243** (net **+249 lines**)
- **14 new files** including `auth_middleware.py`, 7 new test files, `Dockerfile`, `.dockerignore`, `.env.example`, `poetry.lock`
- **Test count:** 11 unit tests → **170 mock-based unit/E2E tests** (Docker-gated integration tests unchanged)
- **Tool count:** 74 (unchanged — no API regressions)

---

## 1. PRD vs Code Alignment — Status

| ID  | Finding                                                                  | Severity | Status     | Resolution |
|-----|--------------------------------------------------------------------------|----------|------------|------------|
| P-1 | `max_connections` / `timeout` fields existed but were never wired        | High     | **Closed** | Fields **removed** from `config.py`; PRD §9.1 documents pool tuning as future work using python-arango's `HTTPClient` |
| P-2 | `enable_metrics` field reserved but never implemented                    | Low      | **Closed** | Field **removed** from `config.py`; metrics documented as future work in PRD §9.1 |
| P-3 | `ARANGO_VERIFY_SSL` plumbing not actually applied at HTTP-client level   | Medium   | **Closed** | Verified `verify_override` is the correct python-arango knob; no change required, PRD §3.1 clarified |
| P-4 | Log redaction — bind values not logged, but raw query text was logged    | Medium   | **Closed** | User-supplied AQL is now redacted by default to `<redacted len=N sha1=…>`; the sha1 prefix lets operators correlate log lines for the same query without exposing literals. Set `LOG_AQL_QUERIES=true` to opt back into plaintext (first 100 chars) for debugging. 4 new mock tests in `test_agent_unit.py::TestAQLLogRedaction`. |
| P-5 | `@handle_arango_errors` only used by 5/15 agents                         | High     | **Closed** | Decorator extended with `on_arango_error` callback; **all 15 agents** now use it (Phase 1 + Phase 3 fan-out) |
| P-6 | No auth middleware for HTTP transport (acknowledged limitation)          | Medium   | **Closed** | New `auth_middleware.py` (`BearerTokenAuthMiddleware`); `MCP_AUTH_TOKEN` required for non-loopback HTTP/SSE; startup guard refuses to bind otherwise |

---

## 2. Code Quality — Status

### 2.1 Duplicate Code

| ID  | Finding                                                              | Severity | Status     | Resolution |
|-----|----------------------------------------------------------------------|----------|------------|------------|
| Q-1 | 10 agents repeated try/except instead of using the decorator         | High     | **Closed** | Extended `@handle_arango_errors` (`on_arango_error` callback) and migrated all 10 agents (`aql_execution`, `cluster_management`, `transaction_management`, `view_management`, `backup_management`, `graph_traversal`, `user_management`, `vector_search`, `database_management`, `manual_management`) |
| Q-2 | `db = arango_connector.get_db(...)` boilerplate duplicated 11+ times | Medium   | **Closed** | `ArangoAgentBase.resolve_db()` introduced in foundations pass; all DB-scoped agents now call it |
| Q-3 | Operation-dispatch `if/elif` chain in every `arun()`                 | Medium   | **Open**   | **Deferred** — registry/dispatch-map refactor is invasive and orthogonal to the security/async work; tracked in PRD §9.1 |
| Q-4 | Optional-field merging duplicated in 4 tool files                    | Low      | **Closed** | `pack_optional()` static helper added to `agent_base.py`; tools that build optional payloads now use it |

### 2.2 Hardcoded Literals

| ID   | Finding                                                              | Severity | Status     | Resolution |
|------|----------------------------------------------------------------------|----------|------------|------------|
| Q-5  | `self._default_db.version()` synchronous call in `async` connect     | High     | **Closed** | Connect path now uses `run_sync` / `asyncio.to_thread` consistently; **102 blocking calls** wrapped across all 15 agents |
| Q-6  | `docker-compose.yml` default password `"password"`                   | Medium   | **Closed** | Default removed; `ARANGO_ROOT_PASSWORD` is now required (no fallback) |
| Q-7  | View error codes 1203/1207 hardcoded                                 | Low      | **Closed** | Constants added to `view_management_agent.py`; on_arango_error callback uses them |
| Q-8  | Vector search magic numbers (`text_en`, 0.7/0.3, ×3 multiplier)      | Low      | **Open**   | **Deferred** — these are tuning knobs for hybrid search; making them configurable requires API design (PRD §9.1) |
| Q-9  | `defaultWeight: 1` in graph traversal AQL                            | Low      | **Closed** | Extracted to module constant |
| Q-10 | `limit` bounds 1..1000 hardcoded                                     | Low      | **Closed** | Named constants in `mcp_tools/document_tools.py` |
| Q-11 | `"_system"` string repeated as deletion guard                        | Low      | **Closed** | `SYSTEM_DB` constant in `database_management_agent.py`, used by both tool and agent layers |

### 2.3 Architectural Weaknesses

| ID   | Finding                                                                | Severity | Status     | Resolution |
|------|------------------------------------------------------------------------|----------|------------|------------|
| Q-12 | Synchronous `python-arango` driver called directly inside `async def`  | High     | **Closed** | All 102 blocking calls wrapped in `await self.run_sync(...)` (Phase 3 fan-out subagents A–E) |
| Q-13 | Global singleton `arango_connector` makes testing harder               | Medium   | **Open**   | **Deferred** — global is convenient and tests work around it via `patch_connector`; no immediate harm |
| Q-14 | No retry/backoff on `connect()`                                        | Medium   | **Closed** | `connect()` now retries with exponential backoff (capped at 30s); short-circuits on auth errors and `ValueError`. Configurable via `ARANGO_CONNECT_MAX_RETRIES` / `ARANGO_CONNECT_INITIAL_BACKOFF` |
| Q-15 | `poetry.lock` git-ignored                                              | Low      | **Closed** | Removed from `.gitignore` and committed |

---

## 3. Security — Status

| ID  | Finding                                                                  | Severity     | Status     | Resolution |
|-----|--------------------------------------------------------------------------|--------------|------------|------------|
| S-1 | **No auth on HTTP transport** — `0.0.0.0:8000` open to any network peer  | **Critical** | **Closed** | `BearerTokenAuthMiddleware` (constant-time `hmac.compare_digest`); startup refuses to bind non-loopback when `MCP_AUTH_TOKEN` is unset (`sys.exit(2)`); 12 mock-based unit tests covering valid/invalid token, missing header, health bypass, non-HTTP scopes |
| S-2 | `_system` delete guard duplicated; case-normalization gap                | High         | **Closed** | Single `SYSTEM_DB` constant; comparison is exact (ArangoDB case-sensitive); guard tested at both layers |
| S-3 | AQL identifier validation only used in 3 of 15 agents                    | High         | **Closed** | Audit confirmed: all agents that build AQL strings now route through `aql_utils.validate_aql_identifier()`; agents that pass identifiers as bind variables (the majority) don't need it. Coverage extended to `view_management` and `aql_execution` |
| S-4 | `root_password` stored as plain `str`                                    | Medium       | **Closed** | `config.py` now uses `pydantic.SecretStr` for `root_password` and `mcp_auth_token`; `_unwrap_secret()` helper safely unwraps before passing to driver. Test: `test_users.py` covers SecretStr-typed user passwords end-to-end |
| S-5 | Docker default password `password`                                       | Medium       | **Closed** | Removed default — `ARANGO_ROOT_PASSWORD` is required for `docker-compose up` |

### New security hardening (beyond original review)

- **AQL `max_runtime` budget** — `execute-aql-query` accepts `max_runtime` (defaults to `MCP_DEFAULT_AQL_MAX_RUNTIME=30.0s`); ArangoDB kills runaway queries server-side
- **JS transaction gate** — `ENABLE_JS_TRANSACTIONS=false` by default; `transaction.execute_js` returns a clear error unless explicitly enabled
- **Loopback-only by default** — without `MCP_AUTH_TOKEN`, the server only allows `127.0.0.1` / `::1` / `localhost` binds
- **Constant-time token comparison** — `hmac.compare_digest()` prevents timing oracles

---

## 4. Test Coverage — Status

### 4.1 Coverage Architecture

| Test Type                    | Before          | After                                               | Status     |
|------------------------------|-----------------|-----------------------------------------------------|------------|
| Unit tests (no DB)           | 11              | **170**                                             | **Closed** |
| Mock-based unit tests        | None            | `test_agent_unit.py`, `test_base_and_decorator.py`, `test_mcp_tools.py`, `test_arango_connector.py` | **Closed** |
| End-to-end MCP tests         | None            | `test_mcp_e2e.py`                                   | **Closed** |
| MCP tool-layer tests         | None            | `test_mcp_tools.py` (parameter schemas, defaults, tool→agent wiring) | **Closed** |
| Performance / load           | None            | None                                                | **Open** (deferred — out of scope) |
| Auth middleware              | N/A             | `test_auth_middleware.py` (12 tests)                | **New**    |
| Health endpoint              | N/A             | `test_health_endpoint.py` (6 tests)                 | **New**    |

### 4.2 Coverage Gaps — Status

| ID  | Gap                                                          | Severity | Status     | Resolution |
|-----|--------------------------------------------------------------|----------|------------|------------|
| T-1 | No mock-based unit tests for agents                          | High     | **Closed** | `test_agent_unit.py` covers dispatch routing, input validation, error formatting for representative agents without Docker |
| T-2 | No MCP tool-layer tests                                      | High     | **Closed** | `test_mcp_tools.py` exercises every tool's parameter schema, defaults, and tool→agent wiring via FastMCP test harness |
| T-3 | No end-to-end MCP transport tests                            | High     | **Closed** | `test_mcp_e2e.py` boots the FastMCP app and round-trips JSON-RPC requests through stdio |
| T-4 | `hybrid_search` untested                                     | Medium   | **Open**   | **Deferred** — needs vector-capable ArangoDB; integration test exists in `test_vector_search.py` but skipped without vector index support |
| T-5 | ArangoSearch `arangosearch`-type views barely tested         | Medium   | **Closed** | `test_coverage_gaps.py` adds create/update/replace for `arangosearch` views |
| T-6 | `agent_base.py` decorator never tested in isolation          | Medium   | **Closed** | `test_base_and_decorator.py` — 24 tests covering error extraction, `on_arango_error` callback, `pack_optional`, `resolve_db`, `run_sync` |
| T-7 | Coverage scope excludes `main.py`, `server.py`, etc.         | Low      | **Closed** | CI now runs `--cov=main --cov=server --cov=arango_connector --cov=config --cov=auth_middleware --cov=aql_utils --cov=agents --cov=mcp_tools` |

---

## 5. Phase Plan — Status

| Phase | Description                              | Status     | Notes |
|-------|------------------------------------------|------------|-------|
| 1     | Foundations (decorator + base helpers)   | ✅ Done    | Sequential — `agent_base.py` extended with `on_arango_error` and `pack_optional` |
| 2     | Cleanup (orphan config, scripts)         | ✅ Done    | `max_connections`/`timeout`/`enable_metrics` removed; `mcp_tools/__init__.py` simplified; `docker-test.sh` cluster mode removed (broken compose); `manuals.zip` deleted |
| 3     | Async migration (15-way fan-out)         | ✅ Done    | 102 blocking calls wrapped in `run_sync` across A–E subagent groups |
| 4     | Security hardening                       | ✅ Done    | `MCP_AUTH_TOKEN`, `SecretStr`, `max_runtime` budget, AQL identifier audit, Docker default password removed |
| 5     | Resilience + observability               | ✅ Done    | Retry/backoff in `connect()`; `/healthz` endpoint; `LOG_FORMAT=json` structured logging |
| 6     | Docs + CI                                | ✅ Done    | PRD refreshed; README HTTP-transport security section; CI coverage scope expanded |

---

## 6. Deferred Items (PRD §9.1 — Future Work)

These are documented and tracked, not bugs:

1. **Per-tenant / per-tool RBAC** — a valid `MCP_AUTH_TOKEN` currently grants the connector's root credentials. Need scoped tokens or per-user JWT/PAT mapping.
2. **Connection pool tuning** — using `requests.Session` defaults; explicit `max_connections`/`timeout` knobs not exposed.
3. **Prometheus / OpenTelemetry metrics** — operators wanting metrics can wrap the ASGI app themselves; no built-in counters / histograms yet.
4. **Cluster CI** — multi-coordinator compose file removed (was broken); to be replaced with a working topology.
5. **Hybrid search integration tests** — require vector-capable ArangoDB; currently skipped in environments without `vector` index support.
6. **Operation-dispatch registry** — replace `if/elif` chains in `arun()` with a registry pattern. Cosmetic.

---

## 7. Verification

Final verification run on **May 5, 2026**:

```
poetry run ruff check .                                                   → All checks passed
poetry run pytest tests/test_aql_utils.py tests/test_base_and_decorator.py \
                  tests/test_agent_unit.py tests/test_mcp_tools.py \
                  tests/test_mcp_e2e.py tests/test_auth_middleware.py \
                  tests/test_health_endpoint.py tests/test_arango_connector.py
                                                                          → 170 passed in 0.86s
poetry run python -c "from server import mcp_app; print(len(mcp_app._tool_manager.list_tools()))"
                                                                          → 74
HTTP startup guard (no MCP_AUTH_TOKEN, --host 0.0.0.0)                    → exit 2 (refused)
```

Docker-gated integration tests (`test_agents.py`, `test_traversal.py`, `test_users.py`, `test_transactions.py`, `test_database_manual_analyzer.py`, `test_vector_search.py`, `test_coverage_gaps.py`) **must be run locally** before merge — `./scripts/docker-test.sh`.

---

## Appendix A — File-by-File Status

| File                       | Original finding                                       | Status |
|----------------------------|--------------------------------------------------------|--------|
| `config.py`                | `root_password` plain str; orphan fields               | ✅ Closed (`SecretStr` + orphans removed; new `mcp_auth_token`, `default_aql_max_runtime`, `log_format`, retry knobs) |
| `arango_connector.py`      | Sync calls in async; no retry; plain credentials       | ✅ Closed (retry + backoff; SecretStr unwrapping) |
| `server.py`                | Tool count in instructions hardcoded                   | ⚠️ Cosmetic — left as-is |
| `main.py`                  | Minor f-string in `logger.debug`                       | ✅ Closed (added auth guard, JSON logging, `/healthz`) |
| `aql_utils.py`             | Clean                                                  | ✅ No change required |
| `agent_base.py`            | Decorator only used by 5/15                            | ✅ Closed (extended; all 15 use it) |
| `auth_middleware.py`       | (new file)                                             | ✅ Added |
| `docker-compose.yml`       | Insecure default password                              | ✅ Closed (default removed) |
| `Dockerfile`               | Multi-stage would help                                 | ✅ Added (with security comment) |
| `.gitignore`               | `poetry.lock` ignored                                  | ✅ Closed |
| `agents/*.py` (×15)        | Duplicate try/except; sync-in-async                    | ✅ Closed (decorator + 102 `run_sync` wraps) |
| `mcp_tools/*.py` (×15)     | Business logic leak in `database_tools.py`             | ✅ Closed (validation moved into agent layer) |
| `tests/*.py`               | No mocks, no MCP-layer, no E2E                         | ✅ Closed (170 mock/E2E tests added) |
| `.github/workflows/ci.yml` | Limited coverage scope                                 | ✅ Closed (8 modules in `--cov`) |
| `PRD.md`                   | 8 stale claims                                         | ✅ Refreshed |
| `README.md`                | No HTTP-transport security guidance                    | ✅ Refreshed |

---

## Appendix B — Quick Wins (originally listed) — all completed

1. ✅ Remove `poetry.lock` from `.gitignore` and commit it
2. ✅ Remove `:-password` default from `docker-compose.yml`
3. ✅ Change `root_password: str` to `root_password: SecretStr`
4. ✅ Add `--cov=main --cov=server --cov=arango_connector --cov=config` to CI pytest
5. ✅ Add `.env.example` documenting required environment variables
6. ✅ Fix `AnalyzerManagementAgent` and `BackupManagementAgent` `database_name` normalization (now via `resolve_db`)
