#!/usr/bin/env bash
# build-lite.sh — construye ov-code-agent-lite:latest (imagen Alpine sin Java/Gradle)
#
# Uso:
#   PAT=<azure-pat> ./build-lite.sh
#   (o define PAT en .env.local)
#
# Variable opcional:
#   REGISTRY — registry destino, e.g. myregistry.azurecr.io (hace push automático)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "${SCRIPT_DIR}/.env.local" ] && source "${SCRIPT_DIR}/.env.local"

: "${PAT:?set PAT in .env.local or environment}"
REGISTRY="${REGISTRY:-}"
TAG="ov-code-agent-lite:latest"

echo "[build-lite] building ${TAG}..."

docker build \
    -f Dockerfile.alpine \
    -t "${TAG}" \
    "${SCRIPT_DIR}"

echo "[build-lite] ${TAG} built OK"

if [ -n "${REGISTRY}" ]; then
    REMOTE_TAG="${REGISTRY}/${TAG}"
    docker tag "${TAG}" "${REMOTE_TAG}"
    docker push "${REMOTE_TAG}"
    echo "[build-lite] pushed → ${REMOTE_TAG}"
fi
