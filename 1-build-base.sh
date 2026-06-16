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
REGISTRY="${REGISTRY:-}"
TAG="ov-agent-base:latest"

# Extraer local-repo si no existe el directorio
if [ ! -d "${SCRIPT_DIR}/gradle/local-repo" ]; then
    echo "[build-base] extrayendo gradle/local-repo.tar.gz..."
    tar -xzf "${SCRIPT_DIR}/gradle/local-repo.tar.gz" -C "${SCRIPT_DIR}/gradle/"
    echo "[build-base] local-repo extraído — $(du -sh "${SCRIPT_DIR}/gradle/local-repo" | cut -f1)"
fi

echo "[build-base] building ${TAG} (esto puede tomar varios minutos la primera vez)..."

docker build \
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
