#!/usr/bin/env bash
set -euo pipefail

# Spin up ArangoDB containers on dynamic ports, run tests, and tear down.
#
# Usage:
#   ./scripts/docker-test.sh              # single-server tests
#   ./scripts/docker-test.sh --cluster    # cluster/sharding tests
#   ./scripts/docker-test.sh --all        # both single + cluster
#   ./scripts/docker-test.sh --image arangodb/arangodb:latest  # override image

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

MODE="--single"
ARANGO_IMAGE="${ARANGO_IMAGE:-arangodb/arangodb:3.12}"
EXTRA_PYTEST_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --single|--cluster|--all)
            MODE="$1"; shift ;;
        --image)
            ARANGO_IMAGE="$2"; shift 2 ;;
        *)
            EXTRA_PYTEST_ARGS+=("$1"); shift ;;
    esac
done

export ARANGO_IMAGE

cleanup() {
    echo "==> Tearing down containers..."
    docker compose --profile cluster down -v 2>/dev/null || true
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
    echo "==> Starting single-server ArangoDB (dynamic port)..."
    docker compose up -d arangodb-single

    wait_for_healthy arangodb-single 60

    local port
    port=$(discover_port arangodb-single 8529)
    echo "==> ArangoDB single-server available on port $port"

    ARANGO_HOSTS="http://localhost:${port}" \
    ARANGO_ROOT_USERNAME="root" \
    ARANGO_ROOT_PASSWORD="test_root_password" \
    ARANGO_DEFAULT_DB_NAME="_system" \
        poetry run pytest tests/ -v -m "not cluster" --tb=short "${EXTRA_PYTEST_ARGS[@]}"

    echo "==> Stopping single-server..."
    docker compose stop arangodb-single
}

run_cluster_tests() {
    echo "==> Starting ArangoDB cluster (dynamic port)..."
    docker compose --profile cluster up -d

    wait_for_healthy coordinator 90

    local port
    port=$(discover_port coordinator 8529)
    echo "==> ArangoDB coordinator available on port $port"

    ARANGO_HOSTS="http://localhost:${port}" \
    ARANGO_ROOT_USERNAME="root" \
    ARANGO_ROOT_PASSWORD="test_root_password" \
    ARANGO_DEFAULT_DB_NAME="_system" \
        poetry run pytest tests/ -v -m "cluster" --tb=short "${EXTRA_PYTEST_ARGS[@]}"
}

case "$MODE" in
    --single)
        run_single_tests
        ;;
    --cluster)
        run_cluster_tests
        ;;
    --all)
        run_single_tests
        cleanup
        run_cluster_tests
        ;;
    *)
        echo "Usage: $0 [--single|--cluster|--all] [--image IMAGE] [pytest args...]"
        exit 1
        ;;
esac

echo "==> All tests passed."
