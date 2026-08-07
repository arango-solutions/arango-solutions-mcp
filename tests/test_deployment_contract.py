"""Static contract tests for the supported container deployment path."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_compose_supports_legacy_or_oidc_auth_and_enables_vector_index():
    compose = _read("docker-compose.yml")

    assert "MCP_AUTH_TOKEN=${MCP_AUTH_TOKEN:-}" in compose
    assert "MCP_OIDC_ISSUER=${MCP_OIDC_ISSUER:-}" in compose
    assert "MCP_ARANGO_CREDENTIALS_JSON=${MCP_ARANGO_CREDENTIALS_JSON:-}" in compose
    assert 'command: ["--experimental-vector-index"]' in compose
    assert "condition: service_healthy" in compose
    assert "${MCP_HTTP_PORT:-8000}:8000" in compose
    assert "${ARANGO_HTTP_PORT:-8529}:8529" in compose
    assert "arangosh --server.endpoint http+tcp://127.0.0.1:8529" in compose
    assert "$$ARANGO_ROOT_PASSWORD" in compose
    assert "http://127.0.0.1:8000/readyz" in compose
    assert "start_period: 15s" in compose


def test_mcp_image_has_dependency_aware_readiness_healthcheck():
    dockerfile = _read("Dockerfile")
    project = _read("pyproject.toml")
    wheel_smoke = _read("scripts/verify_wheel.py")

    assert "HEALTHCHECK" in dockerfile
    assert "http://127.0.0.1:8000/readyz" in dockerfile
    assert "http://127.0.0.1:8000/healthz" not in dockerfile
    assert "start-period=15s" in dockerfile
    assert "FROM python:3.11-alpine3.22 AS builder" in dockerfile
    assert "FROM python:3.11-alpine3.22 AS runtime" in dockerfile
    assert "poetry build --format wheel" in dockerfile
    assert ".venv/bin/pip install --no-deps dist/*.whl" in dockerfile
    assert (
        "COPY --from=builder --chown=root:root " "/opt/arangodb-mcp/.venv /opt/arangodb-mcp/.venv"
    ) in dockerfile
    assert "COPY . ." not in dockerfile
    assert "chmod -R a-w /opt/arangodb-mcp/.venv" in dockerfile
    assert "USER mcp" in dockerfile
    assert 'CMD ["arangodb-mcp"]' in dockerfile
    assert 'packages = [{ include = "arangodb_mcp", from = "src" }]' in project
    assert 'arangodb-mcp = "arangodb_mcp.cli:main"' in project
    assert "src/arangodb_mcp/catalog/tools.yaml" in project
    assert "src/arangodb_mcp/manuals/*.md" in project
    assert '"-I", str(probe)' in wheel_smoke
    assert "root not in package_path.parents" in wheel_smoke
    assert "len(manager.all_registered_tools()) == 81" in wheel_smoke


def test_compose_quick_start_documents_secrets_probes_and_slos():
    readme = _read("README.md")
    slo = _read("docs/slo.md")

    assert "export ARANGO_ROOT_PASSWORD=your_password" in readme
    assert 'export MCP_AUTH_TOKEN="$(openssl rand -hex 32)"' in readme
    assert "curl --fail http://localhost:8000/livez" in readme
    assert "curl --fail http://localhost:8000/readyz" in readme
    assert "`/healthz`" in readme and "deprecated" in readme
    assert "MCP_PROBE_BASE_URL" in readme
    assert "99.9%" in slo
    assert "/livez" in slo and "/readyz" in slo and "/healthz" in slo
    assert "Never reuse ARANGO_ROOT_PASSWORD as the MCP token." in _read(".env.example")


def test_nightly_cluster_workflow_uses_real_multi_server_deployment():
    workflow = _read(".github/workflows/cluster-nightly.yml")

    assert 'cron: "23 3 * * *"' in workflow
    assert "--starter.local" in workflow
    assert "--docker.net-mode=container:arango-cluster-starter" in workflow
    assert "arangodb/arangodb-starter@sha256:" in workflow
    assert "arangodb/arangodb@sha256:" in workflow
    assert "pytest tests/test_cluster.py -m cluster -v" in workflow


def test_phase4_compose_pins_collectors_and_uses_ephemeral_reference_identity():
    compose = _read("docker-compose.phase4.yml")
    idp = _read("tests/integration/phase4/reference_idp.py")
    collector = _read("tests/integration/phase4/otel-collector.yaml")
    prometheus = _read("tests/integration/phase4/prometheus.yml")

    assert "otel/opentelemetry-collector-contrib:0.123.0" in compose
    assert "prom/prometheus:v3.2.1" in compose
    assert "arangodb/arangodb:3.12.4" in compose
    assert 'MCP_OIDC_ALLOW_INSECURE_HTTP: "true"' in compose
    assert "http://reference-idp:8080" in compose
    assert compose.count("healthcheck:") >= 5
    assert "rsa.generate_private_key" in idp
    assert "BEGIN PRIVATE KEY" not in idp
    assert "debug:" in collector and "verbosity: detailed" in collector
    assert 'targets: ["arangodb-mcp:8000"]' in prometheus


def test_phase4_and_phase5_ci_harnesses_make_deployment_contracts_mechanical():
    workflow = _read(".github/workflows/ci.yml")
    runner = _read("scripts/run_phase4_integration.py")

    assert "phase4-integration:" in workflow
    assert "python scripts/run_phase4_integration.py --timeout 300" in workflow
    assert "_free_ports(4)" in runner
    assert '"PHASE4_MCP_PORT": str(mcp_port)' in runner
    assert '"PHASE4_IDP_PORT": str(idp_port)' in runner
    assert '"PHASE4_PROMETHEUS_PORT": str(prometheus_port)' in runner
    assert '"PHASE4_OTEL_HEALTH_PORT": str(otel_health_port)' in runner
    assert '"down", "--volumes", "--remove-orphans"' in runner
    assert "mcp_tool_calls_total" in runner
    assert '("mcp.request", "mcp.tool.call", "arango.database")' in runner

    chart = ROOT / "deploy/helm/arangodb-mcp"
    required_chart_files = {
        "Chart.yaml",
        "values.yaml",
        "values.schema.json",
        "README.md",
        "templates/_helpers.tpl",
        "templates/NOTES.txt",
        "templates/deployment.yaml",
        "templates/service.yaml",
        "templates/serviceaccount.yaml",
        "templates/ingress.yaml",
        "templates/servicemonitor.yaml",
        "templates/secret.yaml",
        "templates/pdb.yaml",
    }
    assert required_chart_files <= {
        str(path.relative_to(chart)) for path in chart.rglob("*") if path.is_file()
    }

    values = yaml.safe_load((chart / "values.yaml").read_text(encoding="utf-8"))
    assert values["secrets"]["existingSecret"] == ""
    assert values["secrets"]["create"]["enabled"] is False
    assert all(
        value == ""
        for key, value in values["secrets"]["create"].items()
        if key not in {"enabled", "extraData"}
    )
    assert values["secrets"]["create"]["extraData"] == {}
    assert values["auth"]["mode"] == "legacy"
    assert values["policy"]["profile"] == "readonly"
    assert values["policy"]["enableJsTransactions"] is False
    assert values["podSecurityContext"]["runAsNonRoot"] is True
    assert values["podSecurityContext"]["seccompProfile"]["type"] == "RuntimeDefault"
    assert values["securityContext"]["allowPrivilegeEscalation"] is False
    assert values["securityContext"]["readOnlyRootFilesystem"] is True
    assert values["securityContext"]["capabilities"]["drop"] == ["ALL"]

    schema = json.loads((chart / "values.schema.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["auth"]["properties"]["mode"]["enum"] == ["legacy", "oidc"]
    assert schema["properties"]["image"]["properties"]["digest"]["pattern"].startswith("^$")

    deployment = (chart / "templates/deployment.yaml").read_text(encoding="utf-8")
    for marker in (
        "secretKeyRef:",
        'eq .Values.auth.mode "legacy"',
        "MCP_AUTH_TOKEN",
        "MCP_OIDC_ISSUER",
        "MCP_ARANGO_CREDENTIALS_JSON",
        "MCP_PROFILE",
        "MCP_DENIED_TOOLS",
        "METRICS_ENABLED",
        "OTEL_TRACES_EXPORTER",
        "path: /livez",
        "path: /readyz",
        "topologySpreadConstraints:",
        "affinity:",
        "resources:",
    ):
        assert marker in deployment
    secret = (chart / "templates/secret.yaml").read_text(encoding="utf-8")
    assert "if .Values.secrets.create.enabled" in secret
    assert "helm.sh/resource-policy: keep" in secret
    assert "required" in secret
    assert "if .Values.ingress.enabled" in _read("deploy/helm/arangodb-mcp/templates/ingress.yaml")
    assert "if .Values.observability.serviceMonitor.enabled" in _read(
        "deploy/helm/arangodb-mcp/templates/servicemonitor.yaml"
    )
    assert "if .Values.podDisruptionBudget.enabled" in _read(
        "deploy/helm/arangodb-mcp/templates/pdb.yaml"
    )

    installer = _read("scripts/install_helm_tools.sh")
    for marker in (
        'HELM_VERSION="v3.18.4"',
        'KUBECONFORM_VERSION="v0.7.0"',
        'KIND_VERSION="v0.29.0"',
        "sha256sum",
        "shasum -a 256",
    ):
        assert marker in installer
    verifier = _read("scripts/verify_helm.sh")
    assert '"$HELM" lint --strict' in verifier
    assert '"$HELM" template' in verifier
    assert '"$KUBECONFORM"' in verifier
    assert "-strict" in verifier

    kind_runner = _read("scripts/run_helm_kind_smoke.sh")
    for marker in (
        "docker build --pull=false",
        "kindest/node:v1.32.5@sha256:",
        '"$KIND" load docker-image',
        "create secret generic phase5-secrets",
        '"$HELM" install',
        '"$HELM" upgrade',
        "curl --fail --show-error",
        '"initialize",',
        '"tools/call"',
        "list-databases",
        '"$KIND" delete cluster',
        "trap cleanup EXIT",
    ):
        assert marker in kind_runner
    arango_fixture = _read("tests/integration/phase5/arangodb.yaml")
    assert "arangodb/arangodb:3.12.4" in arango_fixture
    assert "secretKeyRef:" in arango_fixture
    assert "--experimental-vector-index" in arango_fixture
    assert "helm:" in workflow
    assert "scripts/verify_helm.sh" in workflow
    assert "scripts/run_helm_kind_smoke.sh" in workflow

    release = _read(".github/workflows/release.yml")
    assert ".tools/bin/helm package deploy/helm/arangodb-mcp" in release
    assert "chart-dist/*.tgz" in release

    advisory_route = (
        "https://github.com/arango-solutions/arango-solutions-mcp/security/advisories/new"
    )
    issue_route = "https://github.com/arango-solutions/arango-solutions-mcp/issues"
    assert "@arthurkeen" in _read(".github/CODEOWNERS")
    for document in (
        "CONTRIBUTING.md",
        "SUPPORT.md",
        "SECURITY.md",
        "docs/threat-model.md",
        "docs/deprecation-policy.md",
    ):
        content = _read(document)
        assert issue_route in content or document == "docs/threat-model.md"
        assert advisory_route in content
    assert "not a commercial service-level agreement" in _read("SUPPORT.md")
