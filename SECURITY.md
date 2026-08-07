# Security Policy

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Submit a private report through
[GitHub Security Advisories](https://github.com/arango-solutions/arango-solutions-mcp/security/advisories/new)
with the affected version, reproduction steps, impact, and any suggested mitigation.

Maintainers will acknowledge a report within two business days, assign a severity within five
business days, and provide status updates at least every seven days until resolution.
These are best-effort open-source project response targets, not a commercial service-level
agreement. Scope covers vulnerabilities in this repository's supported code, container, and
Helm chart; third-party infrastructure and unsupported modifications are outside that scope.

Public support requests belong in
[GitHub Issues](https://github.com/arango-solutions/arango-solutions-mcp/issues), following
[SUPPORT.md](SUPPORT.md). The system trust boundaries and residual risks are documented in
[docs/threat-model.md](docs/threat-model.md).

## Supported versions

Security fixes are made on the `main` branch and released in the next 2.x patch. Older major
versions are not supported.

## Severity and remediation

Severity is based on CVSS v3.1, adjusted for exploitability, data exposure, required privileges,
and whether the vulnerable path is enabled by default.

| Severity | Working definition | Remediation target |
| --- | --- | --- |
| Critical | CVSS 9.0-10.0, active exploitation, authentication bypass, remote code execution, or exposed production credentials | Revoke exposed credentials immediately; mitigate within 24 hours and release a fix within 7 calendar days |
| High | CVSS 7.0-8.9 or a practical path to material confidentiality, integrity, or availability impact | Fix or mitigate within 30 calendar days |
| Medium | CVSS 4.0-6.9 with limited impact or significant prerequisites | Fix within 90 calendar days |
| Low | CVSS 0.1-3.9 or defense-in-depth impact | Fix within 180 calendar days or the next planned maintenance release |

CodeQL, dependency audit, Git-history secret scanning, and built-container vulnerability scanning
run in CI. New unexcepted High or Critical dependency, operating-system, or application-library
findings block merge. A detected real credential is revoked and rotated before the finding is
closed; deleting it from the current revision is not sufficient.

## Release supply-chain controls

Official releases are created only by `.github/workflows/release.yml` from a repository tag
whose `vX.Y.Z` value matches `pyproject.toml`. PyPI publication uses GitHub OIDC trusted publishing;
maintainers do not store or use long-lived PyPI API tokens. Containers are published to GHCR by
immutable digest.

Each release includes Python and container SPDX SBOMs, GitHub build-provenance and SBOM
attestations, and a keyless cosign signature for the image digest. The workflow scans the published
digest for High and Critical vulnerabilities and verifies the PyPI wheel hash and isolated install,
container execution, cosign identity, and GitHub attestations before creating the GitHub release.
Consumers should pin the GHCR digest and verify it against the release workflow identity.

## Exceptions

An exception is allowed only when no supported fix exists or an immediate upgrade would cause
greater operational risk. Every exception must be documented beside the scanner suppression and
include:

- the advisory or scanner rule identifier;
- a tracking issue, accountable owner, and approval from a security maintainer;
- the affected component and exposure assessment;
- why remediation is currently infeasible;
- compensating controls; and
- an explicit expiration date.

Critical exceptions expire within 14 days, High within 30 days, Medium within 90 days, and Low
within 180 days. Exceptions are never permanent and must be removed or renewed through a new
review before expiry. Real credentials cannot be excepted. False-positive secret allowlists must
be scoped to the narrowest path and rule or fingerprint and carry the same owner, rationale, and
expiration metadata.

There are no active dependency-audit exceptions. Any future suppression must use the process
above and must not be added as an untracked permanent ignore.

The container scan has two temporary upstream-SBOM false-positive entries in
`.trivyignore.yaml`, tracked by
[issue #5](https://github.com/arango-solutions/arango-solutions-mcp/issues/5). Both expire on
2026-08-20. Runtime probes verify that the reported packages are absent from the final image.
