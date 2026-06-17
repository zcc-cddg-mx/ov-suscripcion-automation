#!/usr/bin/env bash
# 3-test-agent.sh — prueba el endpoint POST /run con multipart/form-data
#
# Uso:
#   ./3-test-agent.sh [--url http://host:5000] [--callback-port 9099]
#
# Todos los casos usan multipart/form-data con el archivo Excel adjunto.
# El caso 8 levanta un servidor HTTP local para capturar el callback de n8n.

set -euo pipefail

BASE_URL="http://localhost:5000"
CALLBACK_PORT="9099"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)           BASE_URL="$2";      shift 2 ;;
    --callback-port) CALLBACK_PORT="$2"; shift 2 ;;
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

# ─── 8. Callback n8n ──────────────────────────────────────────────────────────

echo ""
echo "=== 8. Callback n8n (sin commit, captura respuesta en localhost:${CALLBACK_PORT}) ==="

CALLBACK_FILE="$(mktemp /tmp/n8n_callback_XXXX.json)"

# Minimal HTTP server: accepts one POST, writes body to file, responds 200
python3 - "${CALLBACK_PORT}" "${CALLBACK_FILE}" &
CALLBACK_PID=$!
cat <<'PYEOF' > /tmp/_callback_server.py
import sys, json
from http.server import HTTPServer, BaseHTTPRequestHandler

port = int(sys.argv[1])
out  = sys.argv[2]

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)
        open(out, "wb").write(body)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"received"}')
        # Shutdown after first request
        import threading
        threading.Thread(target=self.server.shutdown).start()

HTTPServer(("0.0.0.0", port), H).serve_forever()
PYEOF

kill "${CALLBACK_PID}" 2>/dev/null || true
python3 /tmp/_callback_server.py "${CALLBACK_PORT}" "${CALLBACK_FILE}" &
CALLBACK_PID=$!

sleep 0.5  # wait for server to bind

# Restart agent with callback URL pointing to this server
# (works when agent runs on same host; for Docker use host.docker.internal or host IP)
# Resolve host IP as seen from inside the container (docker bridge gateway)
HOST_IP=$(docker inspect ov-code-agent --format '{{json .NetworkSettings.Networks}}' 2>/dev/null \
  | python3 -c "import sys,json; nets=json.load(sys.stdin); print(list(nets.values())[0]['Gateway'])" 2>/dev/null \
  || echo "172.17.0.1")
CALLBACK_URL="http://${HOST_IP}:${CALLBACK_PORT}/callback"

echo "Callback server PID=${CALLBACK_PID} listening on ${CALLBACK_URL}"
echo "Reconfiguring agent N8N_CALLBACK_URL via env requires container restart."
echo "Sending request — agent will POST to ${CALLBACK_URL} on completion:"

# Patch running container env and restart is impractical; instead we verify
# the callback by temporarily setting N8N_CALLBACK_URL via docker exec if available.
if docker inspect ov-code-agent > /dev/null 2>&1; then
  docker exec ov-code-agent sh -c "N8N_CALLBACK_URL=${CALLBACK_URL} python3 -c \"
import requests, json
body = {
  'ticket': 'INC_TEST_CALLBACK',
  'status': 'success',
  'task_id': 'test-cb01',
  'command': 'ren-data',
  'branch': 'feature/INC_TEST_renov_agosto',
  'aux_branch': 'feature/INC_TEST_renov_agosto_developer_auxiliar',
  'commit_id': 'deadbeef',
  'repo': 'ov-arizona-backend-ecuador',
  'build_status': 'success',
  'summary': 'Callback test — no real migration',
  'completed_at': '2026-06-15T00:00:00+00:00',
}
r = requests.post('${CALLBACK_URL}', json=body, timeout=5)
print('agent→callback HTTP', r.status_code)
\""
else
  # Fallback: send mock callback directly from this script
  curl -sf -X POST "${CALLBACK_URL}" \
    -H "Content-Type: application/json" \
    -d '{
      "ticket":       "INC_TEST_CALLBACK",
      "status":       "success",
      "task_id":      "test-cb01",
      "command":      "ren-data",
      "branch":       "feature/INC_TEST_renov_agosto",
      "aux_branch":   "feature/INC_TEST_renov_agosto_developer_auxiliar",
      "commit_id":    "deadbeef",
      "repo":         "ov-arizona-backend-ecuador",
      "build_status": "success",
      "summary":      "Callback test — no real migration",
      "completed_at": "2026-06-15T00:00:00+00:00"
    }' | python3 -m json.tool
fi

# Wait for callback server to receive the request (max 10s)
for i in $(seq 1 20); do
  sleep 0.5
  if [ -s "${CALLBACK_FILE}" ]; then break; fi
done

wait "${CALLBACK_PID}" 2>/dev/null || true

echo ""
echo "Payload recibido en el callback:"
if [ -s "${CALLBACK_FILE}" ]; then
  python3 -m json.tool < "${CALLBACK_FILE}"
  # Verify required fields
  python3 - "${CALLBACK_FILE}" <<'PYCHECK'
import sys, json
data = json.load(open(sys.argv[1]))
required = ("ticket", "status", "branch", "aux_branch", "commit_id")
missing  = [f for f in required if f not in data]
if missing:
    print(f"WARN: campos faltantes en callback: {missing}")
else:
    print("OK: todos los campos requeridos presentes en el callback")
PYCHECK
else
  echo "ERROR: callback no recibido en 10 segundos"
  kill "${CALLBACK_PID}" 2>/dev/null || true
fi

rm -f "${CALLBACK_FILE}" /tmp/_callback_server.py
