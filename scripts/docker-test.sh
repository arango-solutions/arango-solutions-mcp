#!/usr/bin/env bash
set -euo pipefail

# Spin up an ArangoDB container on a dynamic port, run tests, and tear down.
#
# Usage:
#   ./scripts/docker-test.sh                                   # run tests
#   ./scripts/docker-test.sh --image arangodb/arangodb:latest  # override image
#   ./scripts/docker-test.sh -k some_test                      # extra pytest args

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

ARANGO_IMAGE="${ARANGO_IMAGE:-arangodb/arangodb:3.12}"
EXTRA_PYTEST_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --single)
            shift ;;
        --image)
            ARANGO_IMAGE="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--single] [--image IMAGE] [pytest args...]"
            exit 0 ;;
        *)
            EXTRA_PYTEST_ARGS+=("$1"); shift ;;
    esac
done

export ARANGO_IMAGE

cleanup() {
    echo "==> Tearing down containers..."
    docker compose down -v 2>/dev/null || true
}
trap cleanup EXIT

wait_for_healthy() {
    local service="$1"
    local timeout="${2:-60}"
    local deadline=$(( $(date +%s) + timeout ))

    echo "==> Waiting for $service to be healthy (timeout ${timeout}s)..."

    while [[ $(date +%s) -lt $deadline ]]; do
        local status
        status=$(docker inspect --format='{{.State.Health.Status}}' "$(docker compose ps -q "$service" 2>/dev/null)" 2>/dev/null || echo "missing")
        if [[ "$status" == "healthy" ]]; then
            return 0
        fi
        sleep 2
    done

    echo "ERROR: $service did not become healthy within ${timeout}s"
    docker compose logs "$service" 2>/dev/null | tail -30
    return 1
}

discover_port() {
    local service="$1"
    local container_port="${2:-8529}"
    # `docker compose port` returns e.g. "0.0.0.0:55123"
    local mapping
    mapping=$(docker compose port "$service" "$container_port" 2>/dev/null)
    echo "${mapping##*:}"
}

run_single_tests() {
    echo "==> Starting ArangoDB (dynamic port)..."
    docker compose up -d arangodb

    wait_for_healthy arangodb 60

    local port
    port=$(discover_port arangodb 8529)
    echo "==> ArangoDB available on port $port"

    ARANGO_HOSTS="http://localhost:${port}" \
    ARANGO_ROOT_USERNAME="root" \
    ARANGO_ROOT_PASSWORD="test_root_password" \
    ARANGO_DEFAULT_DB_NAME="_system" \
        poetry run pytest tests/ -v -m "not cluster" --tb=short "${EXTRA_PYTEST_ARGS[@]}"

    echo "==> Stopping ArangoDB..."
    docker compose stop arangodb
}

run_single_tests

echo "==> All tests passed."
