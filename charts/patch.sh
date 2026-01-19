#!/bin/bash

HELM_BIN=${HELM_BIN:-helm}
HELPER_BIN=${HELPER_BIN:-framework-helper}

ROOT=$(realpath $1)
DEST=$(realpath $2)
shift 2

mkdir -p "${DEST}"

VERSION=$1
REGISTRY=$2

shift 2

for chart in "$@"; do
  # Render patches
  mkdir -p "${ROOT}/patches/${chart}/version"
  echo "[{\"op\":\"replace\",\"path\":\"/version\",\"value\":\"${VERSION}\"}]" > "${ROOT}/patches/${chart}/version/Chart.yaml"

  mkdir -p "${ROOT}/patches/${chart}/image"
  echo "[{\"op\":\"replace\",\"path\":\"/images/application/tag\",\"value\":\"${VERSION}\"},{\"op\":\"replace\",\"path\":\"/images/application/registry\",\"value\":\"${REGISTRY}\"}]" > "${ROOT}/patches/${chart}/image/values.yaml"

  mkdir -p "${ROOT}/results/${chart}"
  ${HELPER_BIN} chart --source "${ROOT}/${chart}" --dest "${ROOT}/results/${chart}" \
    --apply "${ROOT}/patches/${chart}/version" \
    --apply "${ROOT}/patches/${chart}/image"

  ${HELM_BIN} package --destination "${DEST}" "${ROOT}/results/${chart}"
done
