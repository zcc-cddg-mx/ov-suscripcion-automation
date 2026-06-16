#!/usr/bin/env bash
# 3-test-agent.sh — prueba el endpoint POST /run con multipart/form-data
#
# Uso:
#   ./3-test-agent.sh [--url http://host:5000]
#
# Todos los casos usan multipart/form-data con el archivo Excel adjunto.

set -euo pipefail

BASE_URL="http://localhost:5000"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --url) BASE_URL="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXCEL="${SCRIPT_DIR}/requirements/renovaciones/2026/agosto/baseticketAgosto2026.xlsx"

if [ ! -f "${EXCEL}" ]; then
  echo "ERROR: archivo Excel no encontrado: ${EXCEL}"
  exit 1
fi

# ─── helpers ──────────────────────────────────────────────────────────────────

poll() {
  local task_id="$1" max_iter="$2" interval="$3"
  for i in $(seq 1 "${max_iter}"); do
    SRES=$(curl -sf "${BASE_URL}/status/${task_id}")
    STATUS=$(echo "${SRES}" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
    if [[ "${STATUS}" != "queued" && "${STATUS}" != "running" ]]; then
      echo "${SRES}" | python3 -m json.tool
      return
    fi
    printf "  [%ds] status=%s\n" "$((i * interval))" "${STATUS}"
    sleep "${interval}"
  done
  echo "TIMEOUT — last status: ${STATUS}"
}

run_multipart() {
  # Usage: run_multipart ticket year month commit compile
  curl -sf -X POST "${BASE_URL}/run" \
    -F "file=@${EXCEL}" \
    -F "command=ren-data" \
    -F "ticket=$1" \
    -F "year=$2" \
    -F "month=$3" \
    -F "commit=$4" \
    -F "compile=$5"
}

# ─── 1. Health ────────────────────────────────────────────────────────────────

echo "=== 1. Health ==="
curl -sf "${BASE_URL}/health" | python3 -m json.tool

# ─── 2. Campos faltantes → 400 ────────────────────────────────────────────────

echo ""
echo "=== 2. Validación — faltan year y month (debe retornar 400) ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST "${BASE_URL}/run" \
  -F "file=@${EXCEL}" \
  -F "command=ren-data" \
  -F "ticket=INC0001"

echo "Cuerpo del error:"
curl -s -X POST "${BASE_URL}/run" \
  -F "file=@${EXCEL}" \
  -F "command=ren-data" \
  -F "ticket=INC0001" | python3 -m json.tool

# ─── 3. Sin commit ────────────────────────────────────────────────────────────

echo ""
echo "=== 3. POST /run (ren-data, sin commit) ==="
RESP=$(run_multipart "INC0002" 2026 8 false false)
echo "${RESP}" | python3 -m json.tool
TASK_ID=$(echo "${RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

echo "Polling /status/${TASK_ID} (max 1 min)..."
poll "${TASK_ID}" 30 2

# ─── 4. Con commit, sin compile ───────────────────────────────────────────────

echo ""
echo "=== 4. POST /run (ren-data, con commit, sin compile) ==="
RESP=$(run_multipart "INC0002" 2026 8 true false)
echo "${RESP}" | python3 -m json.tool
TASK_ID=$(echo "${RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

echo "Polling /status/${TASK_ID} (max 5 min)..."
poll "${TASK_ID}" 150 2

# ─── 5. Con commit y compile ──────────────────────────────────────────────────

echo ""
echo "=== 5. POST /run (ren-data, con commit, con compile) ==="
RESP=$(run_multipart "INC0003" 2026 8 true true)
echo "${RESP}" | python3 -m json.tool
TASK_ID=$(echo "${RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

echo "Polling /status/${TASK_ID} (max 15 min)..."
poll "${TASK_ID}" 450 2

# ─── 6. Concurrencia ─────────────────────────────────────────────────────────

echo ""
echo "=== 6. Concurrencia — segunda tarea debe ser rechazada ==="
run_multipart "INC0002" 2026 8 true false > /tmp/task1.json &
sleep 0.2
run_multipart "INC0002" 2026 8 true false > /tmp/task2.json
wait

echo "Tarea 1:"
python3 -m json.tool < /tmp/task1.json
echo "Tarea 2 (debe ser rejected):"
python3 -m json.tool < /tmp/task2.json

TASK2_ID=$(python3 -c "import sys,json; print(json.load(open('/tmp/task2.json'))['task_id'])")
sleep 3
echo "Estado final tarea 2:"
curl -sf "${BASE_URL}/status/${TASK2_ID}" | python3 -m json.tool

# ─── 7. Historial ─────────────────────────────────────────────────────────────

echo ""
echo "=== 7. GET /tasks (últimas 10) ==="
curl -sf "${BASE_URL}/tasks?limit=10" | python3 -m json.tool
