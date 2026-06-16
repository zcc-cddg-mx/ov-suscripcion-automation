#!/usr/bin/env bash
# 3-test-agent.sh — prueba el endpoint POST /run con payloads ren-data
#
# Uso:
#   ./3-test-agent.sh

set -euo pipefail

BASE_URL="http://localhost:5000"

echo "=== Health ==="
curl -sf "${BASE_URL}/health" | python3 -m json.tool

echo ""
echo "=== POST /run (ren-data, sin commit) ==="
RESP=$(curl -sf -X POST "${BASE_URL}/run" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "ren-data",
    "ticket": "INC0002",
    "input": "requirements/renovaciones/2026/agosto/baseticketAgosto2026.xlsx",
    "year": 2026,
    "month": 8,
    "commit": false
  }')
echo "${RESP}" | python3 -m json.tool
TASK_ID=$(echo "${RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

echo ""
echo "Polling /status/${TASK_ID} ..."
for i in $(seq 1 30); do
  SRES=$(curl -sf "${BASE_URL}/status/${TASK_ID}")
  STATUS=$(echo "${SRES}" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  if [[ "${STATUS}" != "queued" && "${STATUS}" != "running" ]]; then
    echo "${SRES}" | python3 -m json.tool
    break
  fi
  printf "  [%s] status=%s\n" "${i}" "${STATUS}"
  sleep 2
done

echo ""
echo "=== POST /run (ren-data, con commit, sin compile) ==="
RESP=$(curl -sf -X POST "${BASE_URL}/run" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "ren-data",
    "ticket": "INC0002",
    "input": "requirements/renovaciones/2026/agosto/baseticketAgosto2026.xlsx",
    "year": 2026,
    "month": 8,
    "commit": true,
    "compile": false
  }')
echo "${RESP}" | python3 -m json.tool
TASK_ID=$(echo "${RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

echo ""
echo "Polling /status/${TASK_ID} (max 5 min)..."
for i in $(seq 1 150); do
  SRES=$(curl -sf "${BASE_URL}/status/${TASK_ID}")
  STATUS=$(echo "${SRES}" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  if [[ "${STATUS}" != "queued" && "${STATUS}" != "running" ]]; then
    echo "${SRES}" | python3 -m json.tool
    break
  fi
  printf "  [%ds] status=%s\n" "$((i*2))" "${STATUS}"
  sleep 2
done

echo ""
echo "=== POST /run (ren-data, con commit, con compile) ==="
RESP=$(curl -sf -X POST "${BASE_URL}/run" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "ren-data",
    "ticket": "INC0003",
    "input": "requirements/renovaciones/2026/agosto/baseticketAgosto2026.xlsx",
    "year": 2026,
    "month": 8,
    "commit": true,
    "compile": true
  }')
echo "${RESP}" | python3 -m json.tool
TASK_ID=$(echo "${RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

echo ""
echo "Polling /status/${TASK_ID} (max 10 min)..."
for i in $(seq 1 300); do
  SRES=$(curl -sf "${BASE_URL}/status/${TASK_ID}")
  STATUS=$(echo "${SRES}" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  if [[ "${STATUS}" != "queued" && "${STATUS}" != "running" ]]; then
    echo "${SRES}" | python3 -m json.tool
    break
  fi
  printf "  [%ds] status=%s\n" "$((i*2))" "${STATUS}"
  sleep 2
done

echo ""
echo "=== POST /run (concurrent — should be rejected) ==="
# Send two requests almost simultaneously and check second is rejected
curl -sf -X POST "${BASE_URL}/run" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "ren-data",
    "ticket": "INC0002",
    "input": "requirements/renovaciones/2026/agosto/baseticketAgosto2026.xlsx",
    "year": 2026,
    "month": 8,
    "commit": true,
    "compile": false
  }' > /tmp/task1.json &

sleep 0.2

curl -sf -X POST "${BASE_URL}/run" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "ren-data",
    "ticket": "INC0002",
    "input": "requirements/renovaciones/2026/agosto/baseticketAgosto2026.xlsx",
    "year": 2026,
    "month": 8,
    "commit": true,
    "compile": false
  }' > /tmp/task2.json

wait

echo "Task 1:"
cat /tmp/task1.json | python3 -m json.tool
echo "Task 2 (should be rejected or queued):"
cat /tmp/task2.json | python3 -m json.tool

# Poll task2 for final rejection status
TASK2_ID=$(cat /tmp/task2.json | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
sleep 3
echo "Task 2 final status:"
curl -sf "${BASE_URL}/status/${TASK2_ID}" | python3 -m json.tool
