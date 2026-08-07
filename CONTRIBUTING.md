# Contributing

Thank you for improving the ArangoDB MCP Server.

## Start with an issue

Use [GitHub Issues](https://github.com/arango-solutions/arango-solutions-mcp/issues) for
bug reports, feature proposals, and contribution coordination. Search existing issues first
and include the affected version, deployment mode, expected behavior, actual behavior, and a
minimal reproduction. Do not include credentials, access tokens, customer data, or other
sensitive material.

Suspected vulnerabilities must not be filed publicly. Follow
[SECURITY.md](SECURITY.md) and use
[GitHub private security advisories](https://github.com/arango-solutions/arango-solutions-mcp/security/advisories/new).

## Development workflow

1. Fork the repository and branch from `main`.
2. Install Python 3.10+ and Poetry 2.1.3.
3. Run `poetry install --with dev`.
4. Make a focused change with tests and documentation.
5. Run the relevant local gates before opening a pull request:

```sh
poetry run ruff check .
poetry run ruff format --check .
poetry run python -m mypy --ignore-missing-imports src/arangodb_mcp evals
poetry run pytest tests/ --ignore=tests/test_cluster.py
poetry run python scripts/verify_docs.py
poetry check --lock
```

Helm changes must also pass:

```sh
scripts/install_helm_tools.sh
scripts/verify_helm.sh
```

Run `scripts/run_helm_kind_smoke.sh` when Docker and kind are available. The test creates and
deletes a dedicated kind cluster.

## Pull requests

Keep pull requests reviewable, explain why the change is needed, link its issue, and list
the commands actually run. Update tests and user/operator documentation with behavior
changes. Maintainers may request design changes, additional tests, or a narrower scope.

By contributing, you agree that your contribution is licensed under this repository's
license.
