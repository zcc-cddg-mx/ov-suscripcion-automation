# ov-suscripcion-automation — Code Agent

Agente de código (Step 4) dentro del pipeline de automatización OV Suscripciones.
Recibe solicitudes de migración Flyway desde n8n, genera los archivos, compila y hace push al repo de backend.

```
n8n → POST /run (multipart) → Code Agent → push branch → POST callback → n8n crea PR → Azure DevOps
```

## Tipos de migración soportados

| Tipo | Comando | Módulo destino |
|---|---|---|
| Vencimientos motor | `ren-data` | `ams-policy` |
| Reglas de tarificación | `rules` | `ams-rule` |

Cada migración produce exactamente dos archivos con el mismo nombre base:
- `V{TIMESTAMP}__{TICKET}_{Descripcion}.xlsx`
- `V{TIMESTAMP}__{TICKET}_{Descripcion}.java`

---

## HTTP API

### `POST /run` — encolar tarea

**Content-Type:** `multipart/form-data`

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `file` | archivo | ✓ | Excel base del negocio (baseticketMES.xlsx) |
| `command` | texto | ✓ | `ren-data` o `rules` |
| `ticket` | texto | ✓ | ID del ticket (ej. `ZNRX-67108`) |
| `year` | número | ✓ | Año de la migración |
| `month` | número | ✓ | Mes de la migración |
| `commit` | bool | — | `true` para crear branch y hacer push (default `false`) |
| `compile` | bool | — | `true` para verificar compilación Java antes del push (default `false`) |
| `entity` | texto | — | Solo para `rules` — nombre de la entidad (ej. `VHPlanRules`) |

**Respuesta 202:**
```json
{"status": "queued", "task_id": "a1b2c3d4"}
```

**Respuesta 400** (campos faltantes):
```json
{"status": "error", "error": "Missing required field(s): file, year"}
```

**Respuesta 202 rechazada** (ya hay una tarea corriendo):
```json
{"status": "rejected", "task_id": "...", "active_task": {"task_id": "...", "ticket": "..."}}
```

---

### `GET /status/<task_id>` — consultar estado

```json
{
  "task_id":      "a1b2c3d4",
  "status":       "done",
  "ticket":       "ZNRX-67108",
  "command":      "ren-data",
  "branch":       "feature/ZNRX_67108_renov_agosto",
  "aux_branch":   "feature/ZNRX_67108_renov_agosto_developer_auxiliar",
  "commit_id":    "abc123ef",
  "repo":         "ov-arizona-backend-ecuador",
  "build_status": "success",
  "summary":      "Migration V2026_08_15_... generated and pushed to feature/...",
  "created_at":   "2026-06-15T14:20:00+00:00",
  "updated_at":   "2026-06-15T14:32:00+00:00"
}
```

Estados posibles: `queued` → `running` → `done` | `error` | `rejected`

---

### `GET /tasks?limit=50` — historial

Lista las últimas N tareas (máx 200), más recientes primero. Persiste en SQLite.

---

### `GET /health` — liveness

```json
{"status": "ok", "service": "code-agent"}
```

---

## Callback a n8n

Al terminar cada tarea (éxito o error), el agente hace `POST N8N_CALLBACK_URL` con:

```json
{
  "ticket":       "ZNRX-67108",
  "status":       "success",
  "task_id":      "a1b2c3d4",
  "command":      "ren-data",
  "branch":       "feature/ZNRX_67108_renov_agosto",
  "aux_branch":   "feature/ZNRX_67108_renov_agosto_developer_auxiliar",
  "commit_id":    "abc123ef",
  "repo":         "ov-arizona-backend-ecuador",
  "build_status": "success",
  "summary":      "Migration V2026_08_... generated and pushed to feature/...",
  "completed_at": "2026-06-15T14:32:00+00:00"
}
```

En caso de error: `"status": "error"` + campo `"error"` con el detalle.

---

## Pruebas locales del callback

Para verificar el callback sin conectarse a n8n real:

**Terminal 1 — levantar el mock:**
```bash
python tests/mock_n8n.py
# Listening on http://0.0.0.0:9099/webhook
```

**`.env.local` — activar URL del mock:**
```bash
export N8N_CALLBACK_URL=http://172.17.0.1:9099/webhook
```

**Terminal 2 — reiniciar y probar:**
```bash
./2-start-agent.sh
# enviar prueba desde Bruno o 3-test-agent.sh
```

El mock imprime cada callback recibido con ticket, status y branch.

---

## Docker

### Requisitos previos

- `gradle/local-repo.tar.gz` (384M) — extraer en `gradle/local-repo/` antes de construir la imagen base
- `.env.local` con credenciales (ver `.env.local.example`)

### Variables de entorno

| Variable | Descripción |
|---|---|
| `PAT` | Azure DevOps PAT (git clone + push) |
| `AZURE_USERNAME` | Usuario Azure DevOps (ej. `carlos.duarte2`) |
| `N8N_CALLBACK_URL` | URL webhook n8n (opcional, ej. `https://n8n.host/webhook/...`) |
| `GRADLE_WORKERS_MAX` | Override `gradle.workers.max` (default: `nproc`) |
| `TASKS_DB` | Path DB SQLite (default `/data/tasks.db`) |
| `UPLOADS_DIR` | Directorio uploads (default `/data/uploads`) |

### Flujo de construcción

```bash
# 1. Construir imagen base (una vez — contiene repo + local-repo Maven 455M)
PAT=<azure-pat> AZURE_USERNAME=carlos.duarte2 ./1-build-base.sh

# 2. Construir imagen del agente (~5s)
docker build -t ov-code-agent:latest .

# 3. Arrancar
N8N_CALLBACK_URL=https://n8n.host/webhook/... ./2-start-agent.sh

# 4. Probar
./3-test-agent.sh
```

El volumen `ov-agent-data:/data` persiste la BD SQLite y los archivos subidos entre reinicios.

---

## Estructura del proyecto

```
app.py                       # Flask API — endpoints /run /status /tasks /health
main.py                      # CLI + run_payload() compartido por CLI y API
src/
  generator_ren_data.py      # Generador Tipo 1 (vencimientos motor)
  generator_rules.py         # Generador Tipo 2 (reglas tarificación)
  java_template.py           # Genera la clase Java
  placer.py                  # Copia archivos al repo, crea branch, commit, push
  build_check.py             # Verificación javac antes del push
  task_store.py              # SQLite — persistencia de tareas
  config.py                  # Carga config.json
  logger.py                  # Logs estructurados
fixtures/
  lov_ams_policy.json        # LOV estático ams-policy (289 filas)
  lov_ams_rule.json          # LOV estático ams-rule (25 filas)
gradle/
  repo-local/                # gradle.properties template + setup-local-gradle.sh
  local-repo.tar.gz          # Maven local repo 384M (gitignoreado, distribuir aparte)
Dockerfile                   # ov-code-agent (FROM ov-agent-base + código Python)
Dockerfile.base              # ov-agent-base (OS + Java + Gradle + repo + local-repo)
docker-entrypoint.sh         # Init: config.json, gradle.properties, git checkout, setup-gradle
1-build-base.sh              # Construye ov-agent-base
2-start-agent.sh             # Arranca contenedor
3-test-agent.sh              # 8 casos de prueba (multipart, validación, callback)
```

## Tests unitarios

```bash
conda activate ov-suscripcion
python -m pytest tests/ -v
```
