# QA Agent — Contrato de diseño

> Versión: 1.2 — 2026-06-16  
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
- Recibir el archivo Excel de negocio (`baseticketMES.xlsx`) adjunto por n8n
- Verificar que el servicio DEV responde correctamente tras el deploy
- Verificar que la migración Flyway fue aplicada en la base de datos
- **Validación directa BD:** verificar la integridad de los datos insertados (conteo total + muestra aleatoria de 50 placas — factor y renewal_blocked en tabla de vencimientos)
- **Validación vía API del sistema:** para la misma muestra de 50 placas, llamar al endpoint de cotización/tarificación y verificar que el factor calculado por el motor coincide con la tasa nueva del Excel
- Devolver a n8n un resultado estructurado (aprobado / rechazado + detalle por check y por placa)

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

**Content-Type:** `multipart/form-data`

Igual que el `POST /run` del Code Agent: n8n adjunta el archivo Excel de negocio
junto con los campos de texto del formulario. El archivo se guarda en `/data/uploads/`
antes de encolar la tarea y se usa para construir la muestra de placas (check 6).

#### Campos del formulario

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `file` | archivo | ✓ | Excel de negocio (`baseticketMES.xlsx`) — misma fuente que usó el Code Agent |
| `ticket` | texto | ✓ | ID del ticket Jira |
| `command` | texto | ✓ | `ren-data` o `rules` |
| `module` | texto | ✓ | `ams-policy` o `ams-rule` |
| `migration_name` | texto | ✓ | Nombre completo del archivo Flyway sin extensión |
| `branch` | texto | ✓ | Rama feature creada por el Code Agent |
| `aux_branch` | texto | ✓ | Rama auxiliar |
| `commit_id` | texto | ✓ | Hash del commit con los archivos generados |
| `year` | número | ✓ para `ren-data` | Año de los vencimientos |
| `month` | número | ✓ para `ren-data` | Mes de los vencimientos |
| `entity` | texto | ✓ para `rules` | Nombre de la entidad (ej. `VHPlanRules`) |
| `sample_size` | número | — | Placas a muestrear al azar (default `50`, máx `200`) |
| `callback_url` | texto | — | URL donde n8n espera el resultado; si ausente, usar `N8N_CALLBACK_URL` del env |

Campos requeridos: `file`, `ticket`, `command`, `module`, `migration_name`.
Campos requeridos condicionales: `year` + `month` para `ren-data`; `entity` para `rules`.

#### Respuesta inmediata — 202 Accepted

```json
{"status": "queued", "task_id": "a1b2c3d4"}
```

La validación corre en background; el resultado se envía vía callback (ver §4).

#### Respuesta 400 (campos o archivo faltantes)

```json
{"status": "error", "error": "Missing required field(s): file, migration_name"}
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
  "summary":        "All 6 checks passed — migration applied, 1342 rows validated, 50/50 plate sample OK (BD + API)",
  "checks":         [
    {"name": "flyway_history",   "status": "ok", "detail": "migration recorded in schema_version"},
    {"name": "endpoint_health",  "status": "ok", "detail": "GET /actuator/health → 200"},
    {"name": "row_count",        "status": "ok", "detail": "1342 rows found, expected 1342"},
    {"name": "no_renovar_count", "status": "ok", "detail": "7 'No Renovar' rows found"},
    {"name": "plate_sample",     "status": "ok", "detail": "50/50 plates matched in DB — factor and renewal_blocked correct",
     "sample_size": 50, "passed": 50, "failed": 0},
    {"name": "plate_sample_api", "status": "ok", "detail": "50/50 plates returned correct factor from tariff API",
     "sample_size": 50, "passed": 50, "failed": 0}
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
     "detail": "found 0 'No Renovar' rows, expected >= 1"},
    {"name": "plate_sample",     "status": "failed",
     "detail": "3/50 plates mismatched",
     "sample_size": 50, "passed": 47, "failed": 3,
     "failures": [
       {"plate": "ABC-1234", "field": "factor",          "expected": "0.85",  "found": "0.90"},
       {"plate": "XYZ-9999", "field": "factor",          "expected": "0.72",  "found": null},
       {"plate": "DEF-5678", "field": "renewal_blocked", "expected": "Yes",   "found": "No"}
     ]}
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
FROM <FLYWAY_HISTORY_TABLE>          -- env: FLYWAY_HISTORY_TABLE
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
GET http://<AMS_POLICY_HOST>/<HEALTH_PATH>   (module = ams-policy)
GET http://<AMS_RULE_HOST>/<HEALTH_PATH>     (module = ams-rule)
```

- **Variables:** `AMS_POLICY_HOST`, `AMS_RULE_HOST`, `HEALTH_PATH` (env)
- **Esperado:** HTTP 200, body contiene `"status": "UP"`
- **Fallo si:** código ≠ 200, timeout, o `status` ≠ `"UP"`
- **Aplica a:** `ren-data` y `rules`
- **Timeout:** 10 segundos

---

### 5.3 Check 3 — `row_count` (SQL) — solo `ren-data`

Verifica que el número de filas cargadas coincide con lo esperado.

```sql
SELECT COUNT(*)
FROM <RENEWAL_TABLE>                 -- env: RENEWAL_TABLE
WHERE <RENEWAL_MIGRATION_ID_FIELD> = '<migration_name>';   -- env: RENEWAL_MIGRATION_ID_FIELD
-- Esperado: COUNT = row_count (del request) si se envió, o COUNT > 0
```

- **Fallo si:** `row_count` fue enviado en el request y el conteo difiere
- **Fallo si:** `row_count` no fue enviado y el conteo es 0

---

### 5.4 Check 4 — `no_renovar_count` (SQL) — solo `ren-data`

Verifica que las filas "No Renovar" fueron insertadas con el campo de bloqueo correcto.

```sql
SELECT COUNT(*)
FROM <RENEWAL_TABLE>                         -- env: RENEWAL_TABLE
WHERE <RENEWAL_MIGRATION_ID_FIELD> = '<migration_name>'   -- env: RENEWAL_MIGRATION_ID_FIELD
  AND <RENEWAL_BLOCKED_FIELD> = 'Yes';       -- env: RENEWAL_BLOCKED_FIELD
-- Esperado: COUNT >= 1  (hay al menos 1 fila No Renovar por mes de negocio)
```

- **Fallo si:** COUNT = 0 y el mes tiene filas de negocio cargadas
- **Tolerancia:** se espera entre 2 y 20 filas "No Renovar" por mes normal

---

### 5.5 Check 5 — `entity_rows` (SQL) — solo `rules`

Verifica que la entidad de reglas fue cargada.

```sql
SELECT COUNT(*)
FROM <RULES_TABLE>                           -- env: RULES_TABLE
WHERE <RULES_ENTITY_FIELD> = '<entity>'      -- env: RULES_ENTITY_FIELD
  AND <RULES_MIGRATION_ID_FIELD> = '<migration_name>';  -- env: RULES_MIGRATION_ID_FIELD
-- Esperado: COUNT > 0
```

---

### 5.6 Check 6 — `plate_sample` (SQL) — solo `ren-data`

Verifica que los datos de una muestra aleatoria de placas coinciden exactamente
con los valores del Excel de negocio recibido en el request.

**Algoritmo:**

1. Leer el Excel recibido en `file` (misma lógica que el Code Agent: columnas `CHASIS`, `TASA FINAL`, `PLACAS`)
2. Filtrar únicamente las filas con placa no vacía (`PLACAS`)
3. Seleccionar `sample_size` placas al azar sin reemplazo (`random.sample`)
4. Por cada placa, ejecutar:

```sql
SELECT <RENEWAL_FACTOR_FIELD>,         -- env: RENEWAL_FACTOR_FIELD
       <RENEWAL_BLOCKED_FIELD>          -- env: RENEWAL_BLOCKED_FIELD
FROM   <RENEWAL_TABLE>
WHERE  <RENEWAL_MIGRATION_ID_FIELD> = '<migration_name>'
  AND  <RENEWAL_PLATE_FIELD>        = '<placa>';   -- env: RENEWAL_PLATE_FIELD
```

5. Comparar cada fila DB con la fila del Excel:
   - `factor` — valor numérico normalizado a 8 decimales, o la cadena `'No Renovar'`
   - `renewal_blocked` — `'Yes'` si el factor era `'No Renovar'`, `'No'` en caso contrario

**Resultado por placa:**
- `ok` — ambos campos coinciden exactamente
- `failed` — al menos un campo difiere o la fila no existe en DB (`found: null`)

**Resultado del check:**
- `ok` si `failed == 0`
- `failed` si `failed >= 1` (se reportan todas las discrepancias, no solo la primera)

**Si `sample_size > filas disponibles`:** se usan todas las filas con placa, sin error.

---

### 5.7 Check 7 — `plate_sample_api` (HTTP) — solo `ren-data`

Verifica que el **motor de tarificación** del sistema calcula el factor correcto
para cada placa de la muestra, usando el endpoint de cotización.

Usa la **misma muestra de 50 placas** seleccionada en el check 6 (`plate_sample`).
Ambos checks comparten el sorteo inicial para correlacionar los resultados
(si una placa falla en BD y también en API, queda evidente cuál es la fuente del problema).

**Por cada placa de la muestra:**

```
POST http://<AMS_POLICY_HOST>/<TARIFF_API_PATH>
Content-Type: application/json

{
  "<TARIFF_PLATE_FIELD>":  "<placa>",
  "<TARIFF_CHASIS_FIELD>": "<chasis>"
}
```

- **Variables:** `TARIFF_API_PATH`, `TARIFF_PLATE_FIELD`, `TARIFF_CHASIS_FIELD` (env)
- **Campo de respuesta a leer:** `TARIFF_RESPONSE_FACTOR_FIELD` (env) — ruta al factor en el JSON de respuesta (ej. `"data.factor"` o `"renovacion.tasa"`)
- **Timeout por llamada:** 5 segundos
- **Valor esperado:** el mismo factor del Excel (`TASA FINAL`), normalizado a 8 decimales
- **Placas `No Renovar`:** el motor debería devolver un indicador de bloqueo — el campo esperado y su valor se configuran con `TARIFF_BLOCKED_VALUE` (env)

**Resultado por placa:**
- `ok` — factor devuelto por la API coincide con el Excel
- `failed` — factor difiere, la API devuelve error HTTP, o timeout

**Resultado del check:**
- `ok` si `failed == 0`
- `failed` si `failed >= 1` (se reportan todas las discrepancias)

**Detalle en el callback:**

```json
{
  "name": "plate_sample_api",
  "status": "failed",
  "detail": "2/50 plates returned wrong factor from tariff API",
  "sample_size": 50,
  "passed": 48,
  "failed": 2,
  "failures": [
    {"plate": "ABC-1234", "chasis": "9BWZZZ377VT004251",
     "expected_factor": "0.85000000", "api_factor": "0.90000000",
     "http_status": 200},
    {"plate": "XYZ-9999", "chasis": "9BWZZZ377VT009999",
     "expected_factor": "0.72000000", "api_factor": null,
     "http_status": 500, "error": "internal server error"}
  ]
}
```

---

### Resumen de checks por tipo

| Check | `ren-data` | `rules` | Tipo | Fuente |
|---|---|---|---|---|
| `flyway_history` | ✓ | ✓ | SQL | `migration_name` del request |
| `endpoint_health` | ✓ | ✓ | HTTP | env vars de hosts |
| `row_count` | ✓ | — | SQL | conteo total en DB |
| `no_renovar_count` | ✓ | — | SQL | campo `renewal_blocked` en DB |
| `entity_rows` | — | ✓ | SQL | campo `entity` en DB |
| `plate_sample` | ✓ | — | SQL | muestra aleatoria del Excel vs BD |
| `plate_sample_api` | ✓ | — | HTTP | misma muestra vs endpoint de tarificación |

Los checks 6 y 7 usan **la misma muestra** de `sample_size` placas.

El resultado global es `approved` si **todos** los checks pasan.
Si alguno falla, el resultado es `rejected`.

---

## 6. Variables de entorno

Todas las variables de configuración se pasan al container al desplegarlo.
Nunca se hardcodean en el código.

### Conectividad

| Variable | Descripción | Ejemplo |
|---|---|---|
| `AMS_POLICY_HOST` | Host:puerto del servicio ams-policy en DEV | `ams-policy-dev:8080` |
| `AMS_RULE_HOST` | Host:puerto del servicio ams-rule en DEV | `ams-rule-dev:8080` |
| `HEALTH_PATH` | Path del endpoint de salud (default `/actuator/health`) | `/actuator/health` |
| `DB_DSN` | DSN de conexión a la base de datos DEV | `postgresql://user:pass@db-dev:5432/amsdb` |
| `N8N_CALLBACK_URL` | URL webhook n8n (fallback si `callback_url` no viene en el request) | `https://n8n.host/webhook/qa-result` |

### Esquema de base de datos — `ren-data`

| Variable | Descripción | Ejemplo |
|---|---|---|
| `FLYWAY_HISTORY_TABLE` | Tabla de historial Flyway (default `flyway_schema_history`) | `flyway_schema_history` |
| `RENEWAL_TABLE` | Tabla que contiene las filas de vencimientos cargadas | `frd_fixed_renewal_data` |
| `RENEWAL_MIGRATION_ID_FIELD` | Campo que identifica la migración en `RENEWAL_TABLE` | `migration_id` |
| `RENEWAL_BLOCKED_FIELD` | Campo que indica bloqueo de renovación (`'Yes'`/`'No'`) | `renewal_blocked` |
| `RENEWAL_PLATE_FIELD` | Campo de número de placa en `RENEWAL_TABLE` | `plate_number` |
| `RENEWAL_FACTOR_FIELD` | Campo de factor de renovación en `RENEWAL_TABLE` | `factor` |
| `QA_SAMPLE_SIZE` | Placas a muestrear por defecto (default `50`, máx `200`) | `50` |

### API de tarificación — `ren-data`

| Variable | Descripción | Ejemplo |
|---|---|---|
| `TARIFF_API_PATH` | Path del endpoint de cotización/tarificación | `/api/v1/renovacion/tarificar` |
| `TARIFF_PLATE_FIELD` | Campo de placa en el body del request | `placa` |
| `TARIFF_CHASIS_FIELD` | Campo de chasis en el body del request | `chasis` |
| `TARIFF_RESPONSE_FACTOR_FIELD` | Ruta al factor en la respuesta JSON (notación punto) | `data.factor` |
| `TARIFF_BLOCKED_VALUE` | Valor que indica "No Renovar" en la respuesta de la API | `NO_RENOVAR` |

### Esquema de base de datos — `rules`

| Variable | Descripción | Ejemplo |
|---|---|---|
| `RULES_TABLE` | Tabla que contiene las reglas de tarificación cargadas | `ams_rule_entry` |
| `RULES_ENTITY_FIELD` | Campo de entidad en `RULES_TABLE` | `entity` |
| `RULES_MIGRATION_ID_FIELD` | Campo que identifica la migración en `RULES_TABLE` | `migration_id` |

### Operación

| Variable | Descripción | Default |
|---|---|---|
| `QA_TASKS_DB` | Path SQLite persistencia | `/data/qa_tasks.db` |
| `RETENTION_DAYS` | Días de retención de registros SQLite | `90` |
| `PORT` | Puerto de la API HTTP | `5000` |

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
    input_path     TEXT,                   -- ruta del Excel guardado en /data/uploads/
    sample_size    INTEGER,                -- placas muestreadas
    result         TEXT,                   -- approved / rejected / null
    checks         TEXT,                   -- JSON array de {name, status, detail, ...}
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

La imagen base corporativa es `ams-ubuntu-lite:latest` (igual que el Code Agent).
El QA Agent **no necesita Java ni Gradle** — la imagen es significativamente más
ligera que `ov-agent-base`. Solo requiere Python + el driver de base de datos.

Estructura en dos imágenes (mismo patrón que el Code Agent):

- **`qa-agent-base`** — `ams-ubuntu-lite` + Python venv + pip deps. Se construye
  una vez; solo se reconstruye si cambian dependencias.
- **`ov-qa-agent`** — `FROM qa-agent-base` + código Python. Build en segundos.

```dockerfile
# Dockerfile.base — qa-agent-base
FROM ams-ubuntu-lite:latest

RUN apt-get -qq update && \
    apt-get -qq -y install --no-install-recommends \
        python3-pip python3-venv libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
```

```dockerfile
# Dockerfile — ov-qa-agent
FROM qa-agent-base:latest

WORKDIR /app
COPY . .
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "app.py"]
```

```
# requirements.txt
flask>=3.1
requests>=2.31
psycopg2-binary>=2.9   # ajustar al motor real: pymssql, cx_Oracle, etc.
```

Volumen `/data` para SQLite (igual que el Code Agent):
```bash
docker run -v qa-agent-data:/data ... ov-qa-agent:latest
```

---

## 9. Secuencia de eventos completa

```
1. Azure DevOps pipeline DEV completa (evento o polling en n8n)
2. n8n verifica que el pipeline terminó con éxito
3. n8n llama POST /validate al QA Agent — multipart/form-data:
     file           = baseticketMES.xlsx  (el mismo que envió al Code Agent)
     ticket         = ZNRX-67108
     command        = ren-data
     module         = ams-policy
     migration_name = V2026_06_15_...
     year/month     = 2026/6
4. QA Agent responde 202 {"status": "queued", "task_id": "a1b2c3d4"}
5. Worker QA Agent:
     a. Guarda el Excel en /data/uploads/
     b. Lee todas las filas del Excel (CHASIS, TASA FINAL, PLACAS)
     c. Selecciona sample_size placas al azar con placa no vacía
     d. Ejecuta checks (todos acumulados antes de resolver el resultado global):
          i.   flyway_history    → SQL
          ii.  endpoint_health   → HTTP
          iii. row_count         → SQL  (solo ren-data)
          iv.  no_renovar_count  → SQL  (solo ren-data)
          v.   entity_rows       → SQL  (solo rules)
          vi.  plate_sample      → SQL por cada placa de la muestra (solo ren-data)
          vii. plate_sample_api  → HTTP al endpoint de tarificación por cada placa
                                   de la misma muestra (solo ren-data)
6. QA Agent construye resultado agregado (approved / rejected)
7. QA Agent persiste resultado en SQLite (incluyendo detalle de fallos por placa)
8. QA Agent hace POST callback a n8n con resultado completo
9. n8n procesa resultado:
     approved → actualiza Jira (link PR + "QA passed") → cierra ticket
     rejected → actualiza Jira (detalle de checks + placas fallidas) → reabre / escala
```

---

## 10. Configuración al desplegar

Todos los valores de esquema, tablas y campos se suministran como variables de
entorno al levantar el container — el código no necesita conocerlos de antemano.

El equipo de operaciones / backend debe proveer los valores de las variables de §6
al configurar el container en SERVICIOSIAS. Ejemplo de arranque:

```bash
docker run -d \
  -e AMS_POLICY_HOST=ams-policy-dev:8080 \
  -e AMS_RULE_HOST=ams-rule-dev:8080 \
  -e HEALTH_PATH=/actuator/health \
  -e DB_DSN=postgresql://qa_user:secret@db-dev:5432/amsdb \
  -e FLYWAY_HISTORY_TABLE=flyway_schema_history \
  -e RENEWAL_TABLE=frd_fixed_renewal_data \
  -e RENEWAL_MIGRATION_ID_FIELD=migration_id \
  -e RENEWAL_BLOCKED_FIELD=renewal_blocked \
  -e RENEWAL_PLATE_FIELD=plate_number \
  -e RENEWAL_FACTOR_FIELD=factor \
  -e RULES_TABLE=ams_rule_entry \
  -e RULES_ENTITY_FIELD=entity \
  -e RULES_MIGRATION_ID_FIELD=migration_id \
  -e QA_SAMPLE_SIZE=50 \
  -e TARIFF_API_PATH=/api/v1/renovacion/tarificar \
  -e TARIFF_PLATE_FIELD=placa \
  -e TARIFF_CHASIS_FIELD=chasis \
  -e TARIFF_RESPONSE_FACTOR_FIELD=data.factor \
  -e TARIFF_BLOCKED_VALUE=NO_RENOVAR \
  -e N8N_CALLBACK_URL=https://n8n.genai.zurich.com/webhook/qa-result \
  -v qa-agent-data:/data \
  -p 5000:5000 \
  ov-qa-agent:latest
```

Los valores de ejemplo son ilustrativos — los valores reales los provee el equipo de backend.

---

## 11. Notas de seguridad

- El `DB_DSN` contiene usuario y contraseña — nunca commitearlo; solo en variables de entorno del container
- El QA Agent **solo ejecuta SELECT** — nunca INSERT/UPDATE/DELETE
- Considerar agregar `X-Agent-Token` (misma recomendación que el Code Agent) para que solo n8n pueda llamar al endpoint `/validate`
