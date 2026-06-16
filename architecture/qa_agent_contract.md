# QA Agent — Contrato de diseño

> Versión: 1.0 — 2026-06-15  
> Autor: equipo OV Suscripciones  
> Destinatario: equipo de desarrollo del QA Agent

---

## 1. Rol en el pipeline global

El QA Agent es el **Step 6** del pipeline de automatización (arquitectura v3).
Se activa **después** de que Azure DevOps completa el deploy a DEV.

```
Jira (webhook)
  → n8n
  → Enricher Agent (dentro de n8n)
  → Code Agent          ← genera archivos + push + rama auxiliar
  → n8n                 ← crea PR via Azure CLI/API
  → Azure DevOps        ← pipeline DEV ejecuta Flyway + deploy
  → n8n                 ← detecta pipeline completado, dispara QA
  → QA Agent  ◀ este contrato
       recibe JSON → valida endpoints → valida datos → responde aprobado/rechazado
  → n8n                 ← actualiza Jira (resultado + link PR)
  → Jira                ← cierra ticket si aprobado / reabre si rechazado
```

**Resumen de responsabilidades:**
- Verificar que el servicio DEV responde correctamente tras el deploy
- Verificar que la migración Flyway fue aplicada en la base de datos
- Verificar la integridad de los datos de negocio insertados
- Devolver a n8n un resultado estructurado (aprobado / rechazado + detalle)

El QA Agent **no hace push**, **no crea PRs**, **no modifica código**.
Su única acción externa es leer (HTTP GET + SQL SELECT).

---

## 2. Posición en la red

| Componente | Red | Acceso |
|---|---|---|
| QA Agent (container en SERVICIOSIAS) | Pública | Recibe requests de n8n vía HTTP |
| Servicios DEV (ams-policy, ams-rule) | Interna | QA Agent llega por hostname interno |
| Base de datos DEV | Interna | QA Agent accede por JDBC/psycopg2 |
| n8n | Pública | Recibe callback del QA Agent |

Las URLs de los servicios DEV y el DSN de la base de datos se configuran como variables
de entorno en el container — nunca se hardcodean.

---

## 3. API HTTP del QA Agent

El QA Agent expone una API HTTP mínima, idéntica en estilo al Code Agent.

### 3.1 `POST /validate` — encolar validación

**Content-Type:** `application/json`

#### Body (enviado por n8n tras detectar deploy exitoso)

```json
{
  "ticket":         "ZNRX-67108",
  "command":        "ren-data",
  "module":         "ams-policy",
  "migration_name": "V2026_06_15_14_30_00__ZNRX_67108_VH_ren_data_jun",
  "branch":         "feature/ZNRX_67108_renov_junio",
  "aux_branch":     "feature/ZNRX_67108_renov_junio_developer_auxiliar",
  "commit_id":      "abc123def456",
  "year":           2026,
  "month":          6,
  "row_count":      1342,
  "callback_url":   "https://n8n.genai.zurich.com/webhook/qa-result"
}
```

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `ticket` | string | ✓ | ID del ticket Jira |
| `command` | string | ✓ | `ren-data` o `rules` |
| `module` | string | ✓ | `ams-policy` o `ams-rule` |
| `migration_name` | string | ✓ | Nombre completo del archivo Flyway sin extensión |
| `branch` | string | ✓ | Rama feature creada por el Code Agent |
| `aux_branch` | string | ✓ | Rama auxiliar |
| `commit_id` | string | ✓ | Hash del commit con los archivos generados |
| `year` | int | ✓ para `ren-data` | Año de los vencimientos |
| `month` | int | ✓ para `ren-data` | Mes de los vencimientos |
| `row_count` | int | — | Filas de negocio que debería haber en la migración (para contraste) |
| `entity` | string | ✓ para `rules` | Nombre de la entidad (ej. `VHPlanRules`) |
| `callback_url` | string | — | URL donde n8n espera el resultado; si ausente, usar `N8N_CALLBACK_URL` del env |

#### Respuesta inmediata — 202 Accepted

```json
{"status": "queued", "task_id": "a1b2c3d4"}
```

La validación corre en background; el resultado se envía vía callback (ver §4).

#### Respuesta 400 (campos requeridos faltantes)

```json
{"status": "error", "error": "Missing required field(s): ticket, module"}
```

#### Respuesta 202 rechazada (ya hay una validación en curso)

```json
{
  "status":      "rejected",
  "task_id":     "a1b2c3d4",
  "active_task": {"task_id": "prev1234", "ticket": "ZNRX-67107", "started_at": "..."}
}
```

---

### 3.2 `GET /status/<task_id>` — consultar estado

```json
{
  "task_id":    "a1b2c3d4",
  "status":     "done",
  "ticket":     "ZNRX-67108",
  "command":    "ren-data",
  "module":     "ams-policy",
  "result":     "approved",
  "checks":     [...],
  "created_at": "2026-06-15T14:20:00+00:00",
  "updated_at": "2026-06-15T14:21:30+00:00"
}
```

Estados posibles: `queued` → `running` → `done` | `error`

---

### 3.3 `GET /tasks?limit=50` — historial

Lista las últimas N validaciones (máx 200), más recientes primero.
Persiste en SQLite (`/data/qa_tasks.db`).

---

### 3.4 `GET /health` — liveness

```json
{"status": "ok", "service": "qa-agent"}
```

---

## 4. Callback a n8n al finalizar

Al completar la validación (resultado `approved` o `rejected`), el QA Agent hace
`POST` a la URL en `callback_url` (del request) o a `N8N_CALLBACK_URL` (env).

### 4.1 Resultado aprobado

```json
{
  "ticket":         "ZNRX-67108",
  "status":         "approved",
  "task_id":        "a1b2c3d4",
  "command":        "ren-data",
  "module":         "ams-policy",
  "migration_name": "V2026_06_15_14_30_00__ZNRX_67108_VH_ren_data_jun",
  "branch":         "feature/ZNRX_67108_renov_junio",
  "aux_branch":     "feature/ZNRX_67108_renov_junio_developer_auxiliar",
  "commit_id":      "abc123def456",
  "summary":        "All 4 checks passed — migration applied, 1342 rows validated",
  "checks":         [
    {"name": "flyway_history",   "status": "ok", "detail": "migration recorded in schema_version"},
    {"name": "endpoint_health",  "status": "ok", "detail": "GET /actuator/health → 200"},
    {"name": "row_count",        "status": "ok", "detail": "1342 rows found, expected 1342"},
    {"name": "no_renovar_count", "status": "ok", "detail": "7 'No Renovar' rows found"}
  ],
  "completed_at":   "2026-06-15T14:21:30+00:00"
}
```

### 4.2 Resultado rechazado

```json
{
  "ticket":         "ZNRX-67108",
  "status":         "rejected",
  "task_id":        "a1b2c3d4",
  "command":        "ren-data",
  "module":         "ams-policy",
  "migration_name": "V2026_06_15_14_30_00__ZNRX_67108_VH_ren_data_jun",
  "branch":         "feature/ZNRX_67108_renov_junio",
  "summary":        "2 check(s) failed",
  "checks":         [
    {"name": "flyway_history",   "status": "ok",     "detail": "migration recorded in schema_version"},
    {"name": "endpoint_health",  "status": "ok",     "detail": "GET /actuator/health → 200"},
    {"name": "row_count",        "status": "failed",
     "detail": "found 1300 rows, expected 1342 — 42 rows missing"},
    {"name": "no_renovar_count", "status": "failed",
     "detail": "found 0 'No Renovar' rows, expected >= 1"}
  ],
  "completed_at":   "2026-06-15T14:21:30+00:00"
}
```

### 4.3 Error interno del agente

```json
{
  "ticket":       "ZNRX-67108",
  "status":       "error",
  "task_id":      "a1b2c3d4",
  "error":        "Could not connect to database: connection refused (host=db-dev:5432)",
  "completed_at": "2026-06-15T14:21:30+00:00"
}
```

`status: "error"` significa que el agente no pudo ejecutar los checks (fallo de
infraestructura). Es distinto de `rejected`, que significa que los checks corrieron
pero fallaron por datos incorrectos.

---

## 5. Checks de validación

### 5.1 Check 1 — `flyway_history` (SQL)

Verifica que Flyway registró la migración en su tabla de historial.

```sql
SELECT COUNT(*)
FROM flyway_schema_history
WHERE script LIKE '%<migration_name>%'
  AND success = TRUE;
-- Esperado: COUNT = 1
```

- **Fuente:** `migration_name` del request
- **Fallo si:** COUNT = 0 (migración no aplicada o falló)
- **Aplica a:** `ren-data` y `rules`

---

### 5.2 Check 2 — `endpoint_health` (HTTP)

Verifica que el servicio desplegado responde correctamente.

```
GET http://<AMS_POLICY_HOST>/actuator/health   (module = ams-policy)
GET http://<AMS_RULE_HOST>/actuator/health     (module = ams-rule)
```

- **Esperado:** HTTP 200, body contiene `"status": "UP"`
- **Fallo si:** código ≠ 200, timeout, o `status` ≠ `"UP"`
- **Aplica a:** `ren-data` y `rules`
- **Timeout:** 10 segundos

---

### 5.3 Check 3 — `row_count` (SQL) — solo `ren-data`

Verifica que el número de filas cargadas coincide con lo esperado.

```sql
SELECT COUNT(*)
FROM <tabla_vencimientos>
WHERE migration_id = '<migration_name>';
-- Esperado: COUNT = row_count (del request) si se envió, o COUNT > 0
```

> **Nota para el equipo de desarrollo:** el nombre exacto de la tabla y el campo
> `migration_id` deben confirmarse con el equipo de backend. La tabla objetivo es
> la que Flyway popula a partir del `.xlsx` en `ams-policy/flyway/`.

- **Fallo si:** `row_count` fue enviado en el request y el conteo difiere
- **Fallo si:** `row_count` no fue enviado y el conteo es 0

---

### 5.4 Check 4 — `no_renovar_count` (SQL) — solo `ren-data`

Verifica que las filas "No Renovar" fueron insertadas con el campo de bloqueo correcto.

```sql
SELECT COUNT(*)
FROM <tabla_vencimientos>
WHERE migration_id = '<migration_name>'
  AND renewal_blocked = 'Yes';
-- Esperado: COUNT >= 1  (hay al menos 1 fila No Renovar por mes de negocio)
```

- **Fallo si:** COUNT = 0 y el mes tiene filas de negocio cargadas
- **Tolerancia:** se espera entre 2 y 20 filas "No Renovar" por mes normal

---

### 5.5 Check 5 — `entity_rows` (SQL) — solo `rules`

Verifica que la entidad de reglas fue cargada.

```sql
SELECT COUNT(*)
FROM <tabla_rules>
WHERE entity = '<entity>'
  AND migration_id = '<migration_name>';
-- Esperado: COUNT > 0
```

> **Nota:** el nombre de la tabla y los campos a confirmar con el equipo de backend.

---

### Resumen de checks por tipo

| Check | `ren-data` | `rules` | Tipo |
|---|---|---|---|
| `flyway_history` | ✓ | ✓ | SQL |
| `endpoint_health` | ✓ | ✓ | HTTP |
| `row_count` | ✓ | — | SQL |
| `no_renovar_count` | ✓ | — | SQL |
| `entity_rows` | — | ✓ | SQL |

El resultado global es `approved` si **todos** los checks pasan.
Si alguno falla, el resultado es `rejected`.

---

## 6. Variables de entorno

| Variable | Descripción | Ejemplo |
|---|---|---|
| `AMS_POLICY_HOST` | Host:puerto del servicio ams-policy en DEV | `ams-policy-dev:8080` |
| `AMS_RULE_HOST` | Host:puerto del servicio ams-rule en DEV | `ams-rule-dev:8080` |
| `DB_DSN` | DSN de conexión a la base de datos DEV | `postgresql://user:pass@db-dev:5432/amsdb` |
| `N8N_CALLBACK_URL` | URL webhook n8n (fallback si callback_url no viene en el request) | `https://n8n.host/webhook/qa-result` |
| `QA_TASKS_DB` | Path SQLite persistencia (default `/data/qa_tasks.db`) | `/data/qa_tasks.db` |
| `UPLOADS_DIR` | No aplica — el QA Agent no recibe archivos | — |
| `RETENTION_DAYS` | Días de retención de registros SQLite (default 90) | `90` |
| `PORT` | Puerto de la API HTTP (default 5000) | `5000` |

---

## 7. Persistencia

El QA Agent persiste el historial de validaciones en SQLite, exactamente igual que
el Code Agent. Esquema mínimo de la tabla `qa_tasks`:

```sql
CREATE TABLE IF NOT EXISTS qa_tasks (
    task_id        TEXT PRIMARY KEY,
    ticket         TEXT,
    status         TEXT NOT NULL,          -- queued / running / done / error
    command        TEXT,
    module         TEXT,
    migration_name TEXT,
    branch         TEXT,
    aux_branch     TEXT,
    commit_id      TEXT,
    result         TEXT,                   -- approved / rejected / null
    checks         TEXT,                   -- JSON array de {name, status, detail}
    summary        TEXT,
    error          TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
)
```

---

## 8. Patrones de implementación recomendados

Basados en lo aprendido en el Code Agent (`ov-suscripcion-automation`):

### 8.1 Concurrencia

Un check activo a la vez (mismo patrón que el Code Agent). El lock se adquiere en el
handler HTTP, no en el worker — el rechazo es instantáneo y no crea race conditions.

```python
_lock = threading.Lock()

@app.post("/validate")
def validate():
    if not _lock.acquire(blocking=False):
        return jsonify({"status": "rejected", ...}), 202
    # encolar worker, no liberar el lock hasta que termine
```

### 8.2 Callback con retry

Igual al Code Agent: hasta 3 reintentos con backoff exponencial (2s / 4s / 8s).
El callback **siempre** se dispara en el bloque `finally` del worker, tanto en éxito
como en error.

### 8.3 Logs estructurados

Misma convención `[TAG] mensaje`:

```
[RECV]   task_id=a1b2c3d4 ticket=ZNRX-67108 ACCEPTED
[CHECK]  flyway_history — ok (migration recorded)
[CHECK]  endpoint_health — ok (200 UP)
[CHECK]  row_count — failed (found 1300, expected 1342)
[DONE]   task_id=a1b2c3d4 result=rejected (1 check failed)
[N8N]    callback → https://n8n.host/webhook/qa-result status=200 (attempt 1)
```

### 8.4 Acumulación de errores

Ejecutar **todos** los checks antes de resolver el resultado global — nunca abortar
al primer fallo. n8n y el operador necesitan el reporte completo para diagnosticar.

### 8.5 Docker

Imagen basada en Python + psycopg2 (o el driver apropiado para la base de datos).
Volumen `/data` para SQLite. Sin Gradle/Java — el QA Agent no compila nada.

```dockerfile
FROM python:3.12-slim
RUN apt-get install -y libpq-dev gcc  # para psycopg2
COPY requirements.txt .
RUN pip install flask requests psycopg2-binary
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
```

---

## 9. Secuencia de eventos completa

```
1. Azure DevOps pipeline DEV completa (evento o polling en n8n)
2. n8n verifica que el pipeline terminó con éxito
3. n8n llama POST /validate al QA Agent con ticket + migration_name + row_count
4. QA Agent responde 202 {"status": "queued", "task_id": "a1b2c3d4"}
5. Worker QA Agent ejecuta checks en paralelo (o secuencial, a elección del dev):
     a. flyway_history  → SQL
     b. endpoint_health → HTTP
     c. row_count       → SQL  (solo ren-data)
     d. no_renovar_count → SQL (solo ren-data)
6. QA Agent construye resultado agregado (approved / rejected)
7. QA Agent persiste resultado en SQLite
8. QA Agent hace POST callback a n8n con resultado completo
9. n8n procesa resultado:
     approved → actualiza Jira (link PR + "QA passed") → cierra ticket
     rejected → actualiza Jira (detalle de checks fallidos) → reabre / escala
```

---

## 10. Dudas pendientes a resolver con el equipo de backend

Antes de implementar los checks SQL, el equipo de QA Agent necesita confirmar
con el equipo de backend de OV:

1. **Nombre exacto de la tabla** que Flyway pobla con los datos del `.xlsx` en `ams-policy`
2. **Campo `migration_id`** (o equivalente) para filtrar filas por migración
3. **Campo `renewal_blocked`** (o equivalente) para identificar filas "No Renovar"
4. **Tabla y campos para `rules`** — qué tabla/columnas contienen las reglas de tarificación
5. **Nombre exacto de `flyway_schema_history`** — puede diferir por esquema (`flyway_schema_history` vs `schema_version`)
6. **Credenciales de base de datos DEV** y política de acceso desde SERVICIOSIAS
7. **URL base del actuator** de ams-policy y ams-rule en DEV (`/actuator/health` o `/health`)

---

## 11. Notas de seguridad

- El `DB_DSN` contiene usuario y contraseña — nunca commitearlo; solo en variables de entorno del container
- El QA Agent **solo ejecuta SELECT** — nunca INSERT/UPDATE/DELETE
- Considerar agregar `X-Agent-Token` (misma recomendación que el Code Agent) para que solo n8n pueda llamar al endpoint `/validate`
