#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART="$ROOT/deploy/helm/arangodb-mcp"
ARANGO_MANIFEST="$ROOT/tests/integration/phase5/arangodb.yaml"
TOOLS="$ROOT/.tools/bin"
HELM="${HELM:-$TOOLS/helm}"
KIND="${KIND:-$TOOLS/kind}"
KUBECTL="${KUBECTL:-kubectl}"
CLUSTER_NAME="${PHASE5_CLUSTER_NAME:-arangodb-mcp-phase5}"
NAMESPACE="phase5"
RELEASE="phase5"
NODE_IMAGE="kindest/node:v1.32.5@sha256:e3b2327e3a5ab8c76f5ece68936e4cafaa82edf58486b769727ab0b3b97a5b0d"
IMAGE_REPOSITORY="arangodb-mcp"
IMAGE_TAG="kind-$(git -C "$ROOT" rev-parse --short HEAD)-$(date +%s)"
PORT_FORWARD_PID=""
tmp="$(mktemp -d)"

if [[ ! -x "$HELM" ]]; then HELM="$(command -v helm)"; fi
if [[ ! -x "$KIND" ]]; then KIND="$(command -v kind)"; fi

cleanup() {
  local status=$?
  trap - EXIT
  if [[ "$status" -ne 0 ]]; then
    "$KUBECTL" --namespace "$NAMESPACE" get all 2>/dev/null || true
    "$KUBECTL" --namespace "$NAMESPACE" describe pods 2>/dev/null || true
    "$KUBECTL" --namespace "$NAMESPACE" logs \
      deployment/"$RELEASE"-arangodb-mcp --all-containers 2>/dev/null || true
  fi
  if [[ -n "$PORT_FORWARD_PID" ]]; then
    kill "$PORT_FORWARD_PID" 2>/dev/null || true
    wait "$PORT_FORWARD_PID" 2>/dev/null || true
  fi
  "$KIND" delete cluster --name "$CLUSTER_NAME" >/dev/null 2>&1 || true
  rm -rf "$tmp"
  exit "$status"
}
trap cleanup EXIT

for command in docker "$KUBECTL"; do
  command -v "$command" >/dev/null
done
docker info >/dev/null

"$KIND" delete cluster --name "$CLUSTER_NAME" >/dev/null 2>&1 || true
docker build --pull=false --tag "$IMAGE_REPOSITORY:$IMAGE_TAG" "$ROOT"
"$KIND" create cluster --name "$CLUSTER_NAME" --image "$NODE_IMAGE" --wait 120s
"$KIND" load docker-image "$IMAGE_REPOSITORY:$IMAGE_TAG" --name "$CLUSTER_NAME"

"$KUBECTL" create namespace "$NAMESPACE"
ARANGO_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
MCP_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
"$KUBECTL" --namespace "$NAMESPACE" create secret generic phase5-secrets \
  --from-literal=arango-root-password="$ARANGO_PASSWORD" \
  --from-literal=mcp-auth-token="$MCP_TOKEN"
"$KUBECTL" --namespace "$NAMESPACE" apply -f "$ARANGO_MANIFEST"
"$KUBECTL" --namespace "$NAMESPACE" rollout status deployment/arangodb --timeout=180s

"$HELM" install "$RELEASE" "$CHART" \
  --namespace "$NAMESPACE" \
  --wait \
  --timeout 180s \
  --set-string image.repository="$IMAGE_REPOSITORY" \
  --set-string image.tag="$IMAGE_TAG" \
  --set image.pullPolicy=Never \
  --set-string arango.hosts=http://arangodb:8529 \
  --set-string secrets.existingSecret=phase5-secrets \
  --set-string "server.allowedHosts=127.0.0.1:*\\,$RELEASE-arangodb-mcp:*\\,$RELEASE-arangodb-mcp.$NAMESPACE.svc:*"

"$KUBECTL" --namespace "$NAMESPACE" rollout status \
  deployment/"$RELEASE"-arangodb-mcp --timeout=180s

LOCAL_PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
"$KUBECTL" --namespace "$NAMESPACE" port-forward \
  service/"$RELEASE"-arangodb-mcp "$LOCAL_PORT:80" >"$tmp/port-forward.log" 2>&1 &
PORT_FORWARD_PID=$!

for _ in $(seq 1 30); do
  if curl --fail --silent "http://127.0.0.1:$LOCAL_PORT/livez" >/dev/null; then
    break
  fi
  sleep 1
done
curl --fail --show-error "http://127.0.0.1:$LOCAL_PORT/livez"
curl --fail --show-error "http://127.0.0.1:$LOCAL_PORT/readyz"

BASE_URL="http://127.0.0.1:$LOCAL_PORT" MCP_TOKEN="$MCP_TOKEN" python3 - <<'PY'
import json
import os
import urllib.error
import urllib.request

base_url = os.environ["BASE_URL"]
token = os.environ["MCP_TOKEN"]
protocol = "2026-07-28"


def request(method, params, request_id, authenticated=True, name=None):
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": {
                **params,
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": protocol,
                    "io.modelcontextprotocol/clientCapabilities": {},
                },
            },
        }
    ).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": protocol,
        "MCP-Method": method,
    }
    if authenticated:
        headers["Authorization"] = f"Bearer {token}"
    if name:
        headers["MCP-Name"] = name
    req = urllib.request.Request(f"{base_url}/mcp", data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


status, _ = request("tools/list", {}, 0, authenticated=False)
assert status == 401, status

status, initialized = request(
    "initialize",
    {
        "protocolVersion": protocol,
        "capabilities": {},
        "clientInfo": {"name": "phase5-kind-smoke", "version": "1.0"},
    },
    1,
)
assert status == 200, initialized
assert initialized["result"]["protocolVersion"] == protocol, initialized

status, called = request(
    "tools/call", {"name": "list-databases", "arguments": {}}, 2, name="list-databases"
)
assert status == 200, called
assert "result" in called, called
print("Authenticated MCP initialize and list-databases call passed.")
PY

"$HELM" upgrade "$RELEASE" "$CHART" \
  --namespace "$NAMESPACE" \
  --reuse-values \
  --wait \
  --timeout 180s \
  --set revisionHistoryLimit=4 \
  --set-string podAnnotations.phase5-upgrade="$(date -u +%Y%m%dT%H%M%SZ)"
"$KUBECTL" --namespace "$NAMESPACE" rollout status \
  deployment/"$RELEASE"-arangodb-mcp --timeout=180s
test "$("$HELM" history "$RELEASE" --namespace "$NAMESPACE" --output json | \
  python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')" -eq 2
kill "$PORT_FORWARD_PID" 2>/dev/null || true
wait "$PORT_FORWARD_PID" 2>/dev/null || true
"$KUBECTL" --namespace "$NAMESPACE" port-forward \
  service/"$RELEASE"-arangodb-mcp "$LOCAL_PORT:80" >"$tmp/port-forward-upgrade.log" 2>&1 &
PORT_FORWARD_PID=$!
for _ in $(seq 1 30); do
  if curl --fail --silent "http://127.0.0.1:$LOCAL_PORT/livez" >/dev/null; then
    break
  fi
  sleep 1
done
curl --fail --show-error "http://127.0.0.1:$LOCAL_PORT/readyz"

echo "kind install/upgrade, probes, and authenticated MCP smoke passed."
