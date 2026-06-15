#!/usr/bin/env bash
# build-base.sh — construye ov-agent-base:latest con cache Maven bakeado
#
# Uso:
#   PAT=<azure-pat> ./build-base.sh
#   (o define PAT en .env.local)
#
# Variable opcional:
#   REGISTRY — registry destino, e.g. myregistry.azurecr.io (hace push automático)
#
# Requiere Docker buildx (Docker 20.10+) y el repo backend en ../ov-arizona-backend-ecuador.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "${SCRIPT_DIR}/.env.local" ] && source "${SCRIPT_DIR}/.env.local"

: "${PAT:?set PAT in .env.local or environment}"
: "${AZURE_USERNAME:?set AZURE_USERNAME in .env.local or environment}"
: "${REPO_HOST_PATH:?set REPO_HOST_PATH in .env.local or environment}"
GRADLE_USERNAME="${AZURE_USERNAME}"
REGISTRY="${REGISTRY:-}"
TAG="ov-agent-base:latest"
REPO_PATH="${REPO_HOST_PATH}"

if [ ! -d "${REPO_PATH}/.git" ]; then
    echo "[build-base] ERROR: repo not found at ${REPO_PATH}"
    exit 1
fi

echo "[build-base] building ${TAG} (esto puede tomar varios minutos la primera vez)..."

docker buildx build \
    --build-context "repo=${REPO_PATH}" \
    --build-arg GRADLE_USERNAME="${GRADLE_USERNAME}" \
    --build-arg GRADLE_DEV_PASSWORD="${PAT}" \
    -f Dockerfile.base \
    -t "${TAG}" \
    --load \
    "${SCRIPT_DIR}"

echo "[build-base] ${TAG} built OK"

if [ -n "${REGISTRY}" ]; then
    REMOTE_TAG="${REGISTRY}/${TAG}"
    docker tag "${TAG}" "${REMOTE_TAG}"
    docker push "${REMOTE_TAG}"
    echo "[build-base] pushed → ${REMOTE_TAG}"
fi
