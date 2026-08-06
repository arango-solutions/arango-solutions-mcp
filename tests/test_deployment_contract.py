"""Static contract tests for the supported container deployment path."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_compose_requires_auth_and_enables_vector_index():
    compose = _read("docker-compose.yml")

    assert "MCP_AUTH_TOKEN=${MCP_AUTH_TOKEN:?Set MCP_AUTH_TOKEN before running}" in compose
    assert 'command: ["--experimental-vector-index"]' in compose
    assert "condition: service_healthy" in compose
    assert "${MCP_HTTP_PORT:-8000}:8000" in compose
    assert "${ARANGO_HTTP_PORT:-8529}:8529" in compose
    assert "arangosh --server.endpoint http+tcp://127.0.0.1:8529" in compose
    assert "$$ARANGO_ROOT_PASSWORD" in compose


def test_mcp_image_has_database_backed_healthcheck():
    dockerfile = _read("Dockerfile")

    assert "HEALTHCHECK" in dockerfile
    assert "http://127.0.0.1:8000/healthz" in dockerfile
    assert "start-period=15s" in dockerfile


def test_compose_quick_start_documents_independent_secrets_and_health():
    readme = _read("README.md")

    assert "export ARANGO_ROOT_PASSWORD=your_password" in readme
    assert 'export MCP_AUTH_TOKEN="$(openssl rand -hex 32)"' in readme
    assert "curl --fail http://localhost:8000/healthz" in readme
    assert "Never reuse ARANGO_ROOT_PASSWORD as the MCP token." in _read(".env.example")


def test_nightly_cluster_workflow_uses_real_multi_server_deployment():
    workflow = _read(".github/workflows/cluster-nightly.yml")

    assert 'cron: "23 3 * * *"' in workflow
    assert "--starter.local" in workflow
    assert "--docker.net-mode=container:arango-cluster-starter" in workflow
    assert "arangodb/arangodb-starter@sha256:" in workflow
    assert "arangodb/arangodb@sha256:" in workflow
    assert "pytest tests/test_cluster.py -m cluster -v" in workflow
