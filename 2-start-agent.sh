#!/usr/bin/env bash
# 2-start-agent.sh — levanta el Code Agent (ov-code-agent:latest)
#
# Uso:
#   PAT=<azure-pat> ./2-start-agent.sh
#   (o define PAT en .env.local)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "${SCRIPT_DIR}/.env.local" ] && source "${SCRIPT_DIR}/.env.local"

: "${PAT:?set PAT in .env.local or environment}"
: "${AZURE_USERNAME:?set AZURE_USERNAME in .env.local or environment}"

docker run -d \
  --name ov-code-agent \
  -p 5000:5000 \
  -e GRADLE_USERNAME="${AZURE_USERNAME}" \
  -e GRADLE_DEV_PASSWORD="${PAT}" \
  -e GIT_USERNAME="${AZURE_USERNAME}" \
  -e GIT_PAT="${PAT}" \
  -e REPO_PATH=/repos/ov-arizona-backend-ecuador \
  ov-code-agent:latest

echo "Levantando..."
until curl -sf http://localhost:5000/health > /dev/null 2>&1; do
    printf "."
    sleep 5
done
echo ""
curl -sf http://localhost:5000/health | python3 -m json.tool
