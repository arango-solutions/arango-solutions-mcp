#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART="$ROOT/deploy/helm/arangodb-mcp"
TOOLS="$ROOT/.tools/bin"
HELM="${HELM:-$TOOLS/helm}"
KUBECONFORM="${KUBECONFORM:-$TOOLS/kubeconform}"

if [[ ! -x "$HELM" ]]; then HELM="$(command -v helm)"; fi
if [[ ! -x "$KUBECONFORM" ]]; then KUBECONFORM="$(command -v kubeconform)"; fi

"$HELM" version --short | grep -q '^v3\.18\.4'
"$KUBECONFORM" -v | grep -q 'v0\.7\.0'

"$HELM" lint --strict "$CHART"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

"$HELM" template phase5 "$CHART" \
  --namespace phase5 \
  --kube-version 1.32.0 \
  >"$tmp/default.yaml"

"$HELM" template phase5 "$CHART" \
  --namespace phase5 \
  --kube-version 1.32.0 \
  --set auth.mode=oidc \
  --set-string auth.oidc.issuer=https://id.example.test \
  --set-string auth.oidc.audience=arangodb-mcp \
  --set-string auth.oidc.resourceUrl=https://mcp.example.test/mcp \
  --set ingress.enabled=true \
  --set observability.serviceMonitor.enabled=true \
  --set podDisruptionBudget.enabled=true \
  --set replicaCount=2 \
  >"$tmp/features.yaml"

"$HELM" template phase5 "$CHART" \
  --namespace phase5 \
  --kube-version 1.32.0 \
  --set secrets.create.enabled=true \
  --set-string secrets.create.arangoPassword=disposable-database-password \
  --set-string secrets.create.authToken=disposable-mcp-token \
  >"$tmp/created-secret.yaml"

"$KUBECONFORM" \
  -strict \
  -summary \
  -ignore-missing-schemas \
  -kubernetes-version 1.32.0 \
  "$tmp/default.yaml" "$tmp/features.yaml" "$tmp/created-secret.yaml"

echo "Helm lint, render, and kubeconform checks passed."
