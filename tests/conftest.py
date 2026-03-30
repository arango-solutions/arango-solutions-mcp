"""Shared pytest fixtures for ArangoDB MCP server tests.

Container lifecycle:
    - If ARANGO_HOSTS is set, tests use that existing instance (no Docker).
    - Otherwise, a fresh ArangoDB container is launched on a random free port,
      used for the entire session, and destroyed on teardown.

Environment variables (all optional):
    ARANGO_HOSTS             Existing instance URL (skips Docker launch)
    ARANGO_ROOT_USERNAME     default: root
    ARANGO_ROOT_PASSWORD     default: test_root_password
    ARANGO_IMAGE             default: arangodb/arangodb:3.12
    ARANGO_TEST_TIMEOUT      seconds to wait for container health (default: 120)
"""

import contextlib
import os
import socket
import subprocess
import time
import uuid

# Track whether the user explicitly provided ARANGO_HOSTS before we
# set a dummy value for config validation during test collection.
_USER_PROVIDED_HOSTS = "ARANGO_HOSTS" in os.environ

# Set defaults so that config.py can be imported at collection time
# without raising validation errors.
os.environ.setdefault("ARANGO_HOSTS", "http://localhost:8529")
os.environ.setdefault("ARANGO_ROOT_USERNAME", "root")
os.environ.setdefault("ARANGO_ROOT_PASSWORD", "test_root_password")

import urllib.error  # noqa: E402
import urllib.request  # noqa: E402

import pytest  # noqa: E402
from arango import ArangoClient  # noqa: E402
from arango.database import StandardDatabase  # noqa: E402

_PASSWORD = os.environ.get("ARANGO_ROOT_PASSWORD", "test_root_password")
_USERNAME = os.environ.get("ARANGO_ROOT_USERNAME", "root")
_IMAGE = os.environ.get("ARANGO_IMAGE", "arangodb/arangodb:3.12")
_TIMEOUT = int(os.environ.get("ARANGO_TEST_TIMEOUT", "120"))


def _free_port() -> int:
    """Bind to port 0 and let the OS pick a free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _wait_for_arango(url: str, timeout: int) -> None:
    """Poll the version endpoint until the server responds or timeout.

    Accepts HTTP 200 or 401 — both mean the server process is up and accepting
    TCP connections. Auth failures are expected when authentication is enabled
    (the default since ArangoDB 3.11).
    """
    deadline = time.time() + timeout
    version_url = f"{url}/_api/version"
    while time.time() < deadline:
        try:
            req = urllib.request.Request(version_url)
            base64_creds = (
                __import__("base64").b64encode(f"{_USERNAME}:{_PASSWORD}".encode()).decode()
            )
            req.add_header("Authorization", f"Basic {base64_creds}")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return  # server is up, just auth mismatch — acceptable
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(1)
    raise RuntimeError(f"ArangoDB at {url} did not become healthy within {timeout}s")


def _docker(*args: str) -> str:
    """Run a docker CLI command, return stdout."""
    result = subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


class _ContainerHandle:
    """Tracks a Docker container started by the test session."""

    def __init__(self, container_id: str, host_port: int):
        self.container_id = container_id
        self.host_port = host_port
        self.url = f"http://localhost:{host_port}"

    def teardown(self) -> None:
        subprocess.run(
            ["docker", "rm", "-f", self.container_id],
            capture_output=True,
            timeout=30,
        )


@pytest.fixture(scope="session")
def arango_container():
    """Session-scoped: spin up an ArangoDB container on a random port.

    Yields the _ContainerHandle (or None if using an external instance).
    """
    if _USER_PROVIDED_HOSTS:
        yield None
        return

    port = _free_port()
    container_name = f"mcp-test-{uuid.uuid4().hex[:8]}"

    container_id = _docker(
        "run",
        "-d",
        "--name",
        container_name,
        "-p",
        f"{port}:8529",
        "-e",
        f"ARANGO_ROOT_PASSWORD={_PASSWORD}",
        _IMAGE,
        "--experimental-vector-index",
    )

    handle = _ContainerHandle(container_id, port)

    try:
        _wait_for_arango(handle.url, _TIMEOUT)
        yield handle
    except Exception:
        # Dump logs on failure for debugging
        logs = _docker("logs", "--tail", "50", container_id)
        print(f"\n=== ArangoDB container logs ===\n{logs}\n")
        handle.teardown()
        raise
    else:
        handle.teardown()


@pytest.fixture(scope="session")
def arango_url(arango_container) -> str:
    """Base URL for the ArangoDB instance under test."""
    if arango_container is not None:
        return arango_container.url
    return os.environ["ARANGO_HOSTS"].split(",")[0].strip()


@pytest.fixture(scope="session")
def arango_client(arango_url: str) -> ArangoClient:
    return ArangoClient(hosts=arango_url)


@pytest.fixture(scope="session")
def system_db(arango_client: ArangoClient) -> StandardDatabase:
    """Authenticated handle to _system — used for creating/dropping test DBs."""
    return arango_client.db("_system", username=_USERNAME, password=_PASSWORD)


@pytest.fixture(scope="session")
def arango_version(system_db: StandardDatabase) -> str:
    """Server version string, e.g. '3.12.4'."""
    return system_db.version()


# ── Per-test ephemeral database ───────────────────────────────────────


@pytest.fixture()
def test_db_name() -> str:
    return f"mcp_test_{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def test_db(
    system_db: StandardDatabase,
    arango_client: ArangoClient,
    test_db_name: str,
) -> StandardDatabase:
    """Create an ephemeral database, yield an authenticated handle, then drop it."""
    system_db.create_database(test_db_name)
    db = arango_client.db(test_db_name, username=_USERNAME, password=_PASSWORD)
    yield db  # type: ignore[misc]
    system_db.delete_database(test_db_name, ignore_missing=True)


@pytest.fixture()
def test_collection(test_db: StandardDatabase) -> str:
    """Create a document collection inside the test DB, return its name."""
    name = f"col_{uuid.uuid4().hex[:8]}"
    test_db.create_collection(name)
    return name


@pytest.fixture()
def test_edge_collection(test_db: StandardDatabase) -> str:
    """Create an edge collection inside the test DB, return its name."""
    name = f"edge_{uuid.uuid4().hex[:8]}"
    test_db.create_collection(name, edge=True)
    return name


# ── Connector / Agent wiring ──────────────────────────────────────────


@pytest.fixture()
def patch_connector(
    arango_client: ArangoClient,
    test_db: StandardDatabase,
    test_db_name: str,
    monkeypatch,
):
    """Patch the global arango_connector so agents talk to the ephemeral test DB.

    After this fixture is active, any agent calling ``arango_connector.get_db()``
    (with no argument or with the test DB name) will get the test database handle.
    """
    from arango_connector import arango_connector

    monkeypatch.setattr(arango_connector, "client", arango_client)

    def _get_db(db_name=None):
        if db_name is None or db_name == test_db_name:
            return test_db
        return arango_client.db(db_name, username=_USERNAME, password=_PASSWORD)

    def _get_system_db():
        return arango_client.db("_system", username=_USERNAME, password=_PASSWORD)

    monkeypatch.setattr(arango_connector, "get_db", _get_db)
    monkeypatch.setattr(arango_connector, "get_system_db", _get_system_db)
    monkeypatch.setenv("ARANGO_DEFAULT_DB_NAME", test_db_name)

    return test_db_name


# ── Vector index support detection ────────────────────────────────────


@pytest.fixture(scope="session")
def vector_index_supported(system_db: StandardDatabase, arango_version: str) -> bool:
    """Detect whether the server supports vector indexes (3.12.4+ with --vector-index)."""
    major, minor = [int(x) for x in arango_version.split(".")[:2]]
    if major < 3 or (major == 3 and minor < 12):
        return False
    probe_col = f"vec_probe_{uuid.uuid4().hex[:6]}"
    try:
        system_db.create_collection(probe_col)
        col = system_db.collection(probe_col)
        col.insert({"embedding": [0.0] * 4})
        col.add_index(
            {
                "type": "vector",
                "fields": ["embedding"],
                "params": {"metric": "l2", "dimension": 4, "nLists": 1},
            }
        )
        system_db.delete_collection(probe_col)
        return True
    except Exception:
        with contextlib.suppress(Exception):
            system_db.delete_collection(probe_col, ignore_missing=True)
        return False
