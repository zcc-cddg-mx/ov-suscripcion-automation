#!/usr/bin/env bash
# start-agent.sh — levanta el Code Agent (ov-code-agent:latest)
#
# Uso:
#   GRADLE_DEV_PASSWORD=<pat-azure-artifacts> \
#   GIT_PAT=<pat-azure-repos> \
#   ./start-agent.sh

: "${GRADLE_DEV_PASSWORD:?set GRADLE_DEV_PASSWORD before running}"
: "${GIT_PAT:?set GIT_PAT before running}"

set -euo pipefail

docker run -d \
  --name ov-code-agent \
  -p 5000:5000 \
  -e GRADLE_USERNAME=carlos.duarte2 \
  -e GRADLE_DEV_PASSWORD="${GRADLE_DEV_PASSWORD:?required}" \
  -e GIT_USERNAME=carlos.duarte2 \
  -e GIT_PAT="${GIT_PAT:?required}" \
  -e REPO_PATH=/repos/ov-arizona-backend-ecuador \
  -v /home/idavid/dev/ov/ov-arizona-backend-ecuador:/repos/ov-arizona-backend-ecuador \
  -v /data/gradle-cache:/root/.gradle/caches \
  ov-code-agent:latest

echo "Levantando (warm-up Gradle en curso, puede tardar unos minutos)..."
until curl -sf http://localhost:5000/health > /dev/null 2>&1; do
    printf "."
    sleep 5
done
echo ""
curl -sf http://localhost:5000/health | python3 -m json.tool
