#!/usr/bin/env bash
# 1-build-base.sh — construye ov-agent-base:latest con cache Maven bakeado
#
# Uso:
#   PAT=<azure-pat> ./1-build-base.sh
#   (o define PAT en .env.local)
#
# Variable opcional:
#   REGISTRY — registry destino, e.g. myregistry.azurecr.io (hace push automático)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "${SCRIPT_DIR}/.env.local" ] && source "${SCRIPT_DIR}/.env.local"

: "${PAT:?set PAT in .env.local or environment}"
: "${AZURE_USERNAME:?set AZURE_USERNAME in .env.local or environment}"
REGISTRY="${REGISTRY:-}"
TAG="ov-agent-base:latest"

echo "[build-base] building ${TAG} (esto puede tomar varios minutos la primera vez)..."

docker build \
    --build-arg GRADLE_USERNAME="${AZURE_USERNAME}" \
    --build-arg GRADLE_DEV_PASSWORD="${PAT}" \
    --build-arg GIT_PAT="${PAT}" \
    -f Dockerfile.base \
    -t "${TAG}" \
    "${SCRIPT_DIR}"

echo "[build-base] ${TAG} built OK"

if [ -n "${REGISTRY}" ]; then
    REMOTE_TAG="${REGISTRY}/${TAG}"
    docker tag "${TAG}" "${REMOTE_TAG}"
    docker push "${REMOTE_TAG}"
    echo "[build-base] pushed → ${REMOTE_TAG}"
fi
