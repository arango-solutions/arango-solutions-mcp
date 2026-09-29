#!/usr/bin/env bash
set -Eeuo pipefail

HELM_VERSION="v3.18.4"
KUBECONFORM_VERSION="v0.7.0"
KIND_VERSION="v0.29.0"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${HELM_TOOLS_BIN_DIR:-$ROOT/.tools/bin}"

case "$(uname -s)-$(uname -m)" in
  Linux-x86_64)
    PLATFORM="linux-amd64"
    HELM_SHA256="f8180838c23d7c7d797b208861fecb591d9ce1690d8704ed1e4cb8e2add966c1"
    KUBECONFORM_SHA256="c31518ddd122663b3f3aa874cfe8178cb0988de944f29c74a0b9260920d115d3"
    KIND_SHA256="c72eda46430f065fb45c5f70e7c957cc9209402ef309294821978677c8fb3284"
    ;;
  Darwin-arm64)
    PLATFORM="darwin-arm64"
    HELM_SHA256="041849741550b20710d7ad0956e805ebd960b483fe978864f8e7fdd03ca84ec8"
    KUBECONFORM_SHA256="b5d32b2cb77f9c781c976b20a85e2d0bc8f9184d5d1cfe665a2f31a19f99eeb9"
    KIND_SHA256="314d8f1428842fd1ba2110fd0052a0f0b3ab5773ab1bdcdad1ff036e913310c9"
    ;;
  *)
    echo "Pinned installer supports Linux x86_64 and macOS arm64." >&2
    exit 2
    ;;
esac

mkdir -p "$BIN_DIR"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

verify() {
  local expected="$1"
  local path="$2"
  local actual
  if command -v sha256sum >/dev/null; then
    actual="$(sha256sum "$path" | awk '{print $1}')"
  else
    actual="$(shasum -a 256 "$path" | awk '{print $1}')"
  fi
  [[ "$actual" == "$expected" ]]
}

curl --fail --silent --show-error --location \
  "https://get.helm.sh/helm-${HELM_VERSION}-${PLATFORM}.tar.gz" \
  --output "$tmp/helm.tar.gz"
verify "$HELM_SHA256" "$tmp/helm.tar.gz"
tar -xzf "$tmp/helm.tar.gz" -C "$tmp"
install -m 0755 "$tmp/$PLATFORM/helm" "$BIN_DIR/helm"

curl --fail --silent --show-error --location \
  "https://github.com/yannh/kubeconform/releases/download/${KUBECONFORM_VERSION}/kubeconform-${PLATFORM}.tar.gz" \
  --output "$tmp/kubeconform.tar.gz"
verify "$KUBECONFORM_SHA256" "$tmp/kubeconform.tar.gz"
tar -xzf "$tmp/kubeconform.tar.gz" -C "$tmp"
install -m 0755 "$tmp/kubeconform" "$BIN_DIR/kubeconform"

curl --fail --silent --show-error --location \
  "https://github.com/kubernetes-sigs/kind/releases/download/${KIND_VERSION}/kind-${PLATFORM}" \
  --output "$tmp/kind"
verify "$KIND_SHA256" "$tmp/kind"
install -m 0755 "$tmp/kind" "$BIN_DIR/kind"

"$BIN_DIR/helm" version --short
"$BIN_DIR/kubeconform" -v
"$BIN_DIR/kind" version
