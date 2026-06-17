#!/usr/bin/env bash
# start-lite.sh — levanta ov-code-agent-lite:latest (imagen Alpine)
#
# Uso:
#   PAT=<azure-pat> ./start-lite.sh
#   (o define PAT y AZURE_USERNAME en .env.local)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "${SCRIPT_DIR}/.env.local" ] && source "${SCRIPT_DIR}/.env.local"

: "${PAT:?set PAT in .env.local or environment}"
: "${AZURE_USERNAME:?set AZURE_USERNAME in .env.local or environment}"

docker run -d \
  --name ov-code-agent-lite \
  -p 5000:5000 \
  -e GIT_USERNAME="${AZURE_USERNAME}" \
  -e GIT_PAT="${PAT}" \
  ${N8N_CALLBACK_URL:+-e N8N_CALLBACK_URL="${N8N_CALLBACK_URL}"} \
  ${BUSINESS_EXCEL_PASSWORD:+-e BUSINESS_EXCEL_PASSWORD="${BUSINESS_EXCEL_PASSWORD}"} \
  -v ov-agent-data:/data \
  -v ov-repo-lite:/repos \
  ov-code-agent-lite:latest

echo "Levantando (primer arranque clona el repo — puede tardar 1-2 min)..."
until curl -sf http://localhost:5000/health > /dev/null 2>&1; do
    printf "."
    sleep 5
done
echo ""
curl -sf http://localhost:5000/health | python3 -m json.tool
