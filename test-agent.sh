#!/usr/bin/env bash
# test-agent.sh — prueba el endpoint POST /run con payloads ren-data
#
# Uso:
#   ./test-agent.sh

set -euo pipefail

echo "=== Health ==="
curl -sf http://localhost:5000/health | python3 -m json.tool

echo ""
echo "=== POST /run (ren-data, sin commit) ==="
curl -sf -X POST http://localhost:5000/run \
  -H "Content-Type: application/json" \
  -d '{
    "command": "ren-data",
    "ticket": "INC99999",
    "input": "requirements/renovaciones/2026/agosto/baseticketAgosto2026.xlsx",
    "year": 2026,
    "month": 8,
    "commit": false
  }' | python3 -m json.tool

echo ""
echo "=== POST /run (ren-data, con commit + build) ==="
echo "Nota: primera ejecucion puede tardar ~2-3 min si el cache Gradle esta vacio."
curl -sf -X POST http://localhost:5000/run \
  -H "Content-Type: application/json" \
  -d '{
    "command": "ren-data",
    "ticket": "INC99999",
    "input": "requirements/renovaciones/2026/agosto/baseticketAgosto2026.xlsx",
    "year": 2026,
    "month": 8,
    "commit": true
  }' | python3 -m json.tool
