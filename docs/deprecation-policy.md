# Deprecation policy

The project evolves HTTP protocol behavior, MCP tools, configuration, container images, and
the Helm chart while preserving a practical migration path.

## Policy

- A deprecation is documented in the changelog and release notes with the replacement,
  migration steps, and earliest removal release/date.
- Public configuration, tool names, result contracts, HTTP paths, and chart values normally
  receive at least one minor-release cycle and 90 calendar days of notice.
- Removal that requires incompatible user action occurs in a major release unless a stated
  compatibility window already defines the removal date.
- Security vulnerabilities, unsafe defaults, upstream removals, or behavior that risks data
  corruption may require an accelerated deprecation. The release notes will explain why and
  provide the safest available migration.
- Deprecated behavior remains tested during its compatibility window. New features should
  use the replacement path.

The legacy MCP result contract currently expires on 2027-02-01. The `/healthz` compatibility
probe is deprecated in favor of `/readyz`; `/livez` remains the process-liveness endpoint.

## Helm upgrades

Chart value removals or renames follow the same notice policy. Upgrade notes identify changed
defaults and Secret key migrations. Operators should render and validate each upgrade, pin
the application image by digest, use `helm upgrade --atomic`, and keep the prior release
revision available for rollback. Database and Secret rollback remain operator responsibilities.

## Feedback

Open a [GitHub issue](https://github.com/arango-solutions/arango-solutions-mcp/issues) if a
planned removal creates an unreasonable migration burden. Vulnerability concerns must use
[GitHub private security advisories](https://github.com/arango-solutions/arango-solutions-mcp/security/advisories/new),
not a public issue.
