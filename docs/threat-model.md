# Threat model

## Scope and assets

This model covers the MCP HTTP service, its container and Helm deployment, authentication
middleware, tool policy, ArangoDB credentials, OIDC metadata/JWKS retrieval, telemetry
exports, and the release supply chain. ArangoDB itself, the identity provider, ingress
controller, Kubernetes control plane, and external secret managers are dependencies with
their own threat models.

Assets include database data and availability, ArangoDB and MCP credentials, actor identity
and database scope, confirmation keys, tool-policy configuration, audit/telemetry data,
container integrity, and release provenance.

## Trust boundaries and actors

- Untrusted MCP clients cross the public HTTP/ingress boundary.
- OIDC tokens cross from an external identity provider into the resource server.
- The MCP Pod crosses a network boundary to ArangoDB and optional OTLP/OpenAI endpoints.
- Kubernetes administrators and secret controllers place configuration and credentials into
  the Pod.
- Maintainers and GitHub Actions produce Python, container, and Helm release artifacts.

Legitimate users may be buggy or malicious. Attackers may have network access, stolen bearer
tokens, crafted MCP/AQL input, a compromised dependency, or read access to logs. Cluster
administrators and repository maintainers are privileged and are not fully isolated by this
application.

## Primary threats and controls

### Authentication and confused-deputy attacks

Legacy bearer mode is a shared identity and should be limited to controlled deployments.
OIDC validates issuer, audience, time bounds, asymmetric signatures, and actor/database claims.
Trusted server-side credential mappings prevent JWT claims from supplying ArangoDB passwords.
The server rejects simultaneous legacy and OIDC modes. DNS rebinding Host/Origin checks reduce
browser-driven attacks; ingress hostnames must be added explicitly.

Residual risk: token theft remains usable until expiry or rotation. Use short-lived OIDC tokens,
TLS at every untrusted hop, least-privilege database users, and prompt credential rotation.

### Excessive tool or database authority

Profiles, toolset selection, tool/category denylists, database allowlists, confirmation tokens,
query runtime limits, concurrency/rate limits, and disabled-by-default JavaScript transactions
reduce impact. Deploy `readonly` by default and use distinct database users per actor.

Residual risk: administrators can intentionally select `admin` or enable destructive features.
Policy changes require normal deployment review and audit.

### Injection, resource exhaustion, and data disclosure

Parameterized AQL paths, input validation, body limits, query deadlines, and per-actor/global
limits constrain malicious requests. Query text logging is disabled because literals may contain
secrets. Metrics and traces must not include credentials or unbounded user content.

Residual risk: valid expensive graph/search operations can still consume database resources.
Apply ArangoDB-side permissions, quotas, query controls, and network isolation.

### Secret exposure

Production Helm defaults reference an existing Secret. Service-account token mounting is
disabled, chart-created Secret mode is explicit, and docs warn that Helm release history stores
provided values. Secret values are passed only through `secretKeyRef`; logs must remain redacted.

Residual risk: users with Pod creation, Secret read, node, backup, or Helm release access may
recover credentials. Use an external secret manager, namespace RBAC, encryption at rest, audit
logging, and rotation. Restart Pods after external Secret rotation.

### Container and cluster compromise

The chart runs non-root with a read-only root filesystem, RuntimeDefault seccomp, no privilege
escalation, all Linux capabilities dropped, no service-account token, resource limits, and only
an ephemeral writable `/tmp`. NetworkPolicy is intentionally cluster-specific and must be
supplied by operators to restrict ingress and egress.

Residual risk: kernel/container-runtime vulnerabilities and unrestricted network egress remain
cluster responsibilities. Pin images by digest and use admission, runtime, and network controls.

### Dependency and release compromise

CI is configured to run lint, tests, secret/history scans, dependency and container scans, Helm
rendering/schema validation, and kubeconform; the kind install/upgrade smoke has also passed
locally. The release workflow is configured to attach SBOMs, provenance attestations, and digest
signatures, but those controls have no published-artifact evidence yet. CODEOWNERS locally routes
deployment/release changes for review; its public enforcement begins only after publication and
repository branch/ruleset configuration.

Residual risk: GitHub, actions, registries, package indexes, or maintainer accounts may be
compromised. Enforce branch protection, least-privilege workflow permissions, MFA, pinned
dependencies/actions, and independent attestation verification.

## Security assumptions

Operators provide a supported Kubernetes cluster, TLS termination, secure DNS, namespace RBAC,
an available ArangoDB service, and correctly scoped credentials. Readiness proves connectivity,
not authorization for every MCP operation or database health beyond the connector check.

## Reporting

Do not open a public issue for a suspected vulnerability. Use
[GitHub private security advisories](https://github.com/arango-solutions/arango-solutions-mcp/security/advisories/new)
as described in [SECURITY.md](../SECURITY.md).
