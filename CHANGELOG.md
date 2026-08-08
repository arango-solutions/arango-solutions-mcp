# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

> **BREAKING — MCP clients must update their launch command.** The repository moved to an
> installable `src/arangodb_mcp` package, which **removes the top-level `main.py`** that MCP
> client configs have historically launched. A config still pointing at `main.py` fails to
> start, and because the shared-memory skills are fail-open by design the symptom is silent:
> tools simply disappear, recall/save degrade politely, and nothing is written. Update the
> `arangodb-memory-mcp` entry in `~/.claude.json` **and** `~/.cursor/mcp.json`:
>
> ```diff
> - "args": ["-c", "cd /path/to/arango-solutions-mcp-server && exec .venv/bin/python main.py"]
> + "args": ["-c", "cd /path/to/arango-solutions-mcp-server && exec .venv/bin/arangodb-mcp"]
> ```
>
> Then fully restart Claude Code / reload Cursor — an already-running client keeps its dead
> connection. Verify with `.venv/bin/python <shared-memory>/scripts/verify.py` (expects
> `ALL CHECKS PASSED`). Installed distributions get the `arangodb-mcp` command on `PATH`, so
> `"command": "arangodb-mcp"` with no `args` also works.
>
> **BREAKING — `MCP_PROFILE` now defaults to `readonly` (17 of 81 tools).** The v3 policy layer
> gates tools by profile, and `readonly` excludes every write operation *and* the entire `memory`
> category (`pattern-search`, `save-pattern`, `pattern-applied`, `save-drift-alert`, `embed-*`).
> Clients that relied on the previous always-on surface lose those tools with no error — the
> shared-memory skills fail open, so sessions simply stop recalling and saving. Shared-memory
> users must set the profile explicitly in the same `env` block:
>
> ```json
> "MCP_PROFILE": "developer",
> "MCP_TOOLSETS": "graph,search"
> ```
>
> `developer` = read + write + `memory` + `transaction`, no admin. `graph` / `search` are additive
> toolsets (traversals; vector + hybrid search). Confirm after restart: the server instructions
> report `N active of 81 cataloged tools` with the resolved profile — `developer` + `graph,search`
> yields 61.

### Added

- Installable `arangodb_mcp` source package and `arangodb-mcp` console command.
- Wheel-only isolated installation and package-data verification gate.
- Tag release automation for PyPI trusted publishing, GHCR digest publication, SPDX SBOMs,
  GitHub attestations, keyless cosign signing, Trivy scanning, and post-publication verification.

### Changed

- Catalog metadata and AQL manuals are distributed as package data and loaded through
  `importlib.resources`.
- The container runtime installs the built wheel into a read-only, non-root virtual environment
  instead of copying repository source.

### Removed

- Top-level `main.py`, `server.py`, `config.py`, `arango_connector.py`, `auth_middleware.py`,
  `aql_utils.py`, and the flat `agents/`, `mcp_tools/`, `manuals/` trees. All of these now live
  under `src/arangodb_mcp/`. Anything importing them by their old flat paths — or launching
  `main.py` directly — must be updated; see the migration note at the top of this release.

### Security

- Release jobs use job-scoped least privileges, short-lived OIDC credentials, immutable image
  digests, provenance attestations, and signature identity verification.
