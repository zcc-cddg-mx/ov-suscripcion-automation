#!/usr/bin/env bash
# 1-build-agent.sh — construye ov-code-agent:latest (imagen Alpine sin Java/Gradle)
#
# Uso:
#   PAT=<azure-pat> ./1-build-agent.sh
#   (o define PAT en .env.local)
#
# Variable opcional:
#   REGISTRY — registry destino, e.g. myregistry.azurecr.io (hace push automático)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "${SCRIPT_DIR}/.env.local" ] && source "${SCRIPT_DIR}/.env.local"

: "${PAT:?set PAT in .env.local or environment}"
REGISTRY="${REGISTRY:-}"
TAG="ov-code-agent:latest"

echo "[build-agent] building ${TAG}..."

docker build \
    -f Dockerfile \
    -t "${TAG}" \
    "${SCRIPT_DIR}"

echo "[build-agent] ${TAG} built OK"

if [ -n "${REGISTRY}" ]; then
    REMOTE_TAG="${REGISTRY}/${TAG}"
    docker tag "${TAG}" "${REMOTE_TAG}"
    docker push "${REMOTE_TAG}"
    echo "[build-agent] pushed → ${REMOTE_TAG}"
fi
