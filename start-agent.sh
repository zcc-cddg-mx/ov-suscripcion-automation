#!/usr/bin/env bash
# start-agent.sh — levanta el Code Agent (ov-code-agent:latest)
#
# Uso:
#   GRADLE_DEV_PASSWORD=<pat-azure-artifacts> \
#   GIT_PAT=<pat-azure-repos> \
#   ./start-agent.sh

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

echo "Levantando..."
sleep 3
curl -sf http://localhost:5000/health | python3 -m json.tool
