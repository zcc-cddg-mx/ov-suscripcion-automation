# Reporte Técnico — Code Agent (OV Suscripcion Automation)

**Fecha:** Junio 2026  
**Versión del agente:** 1.2  
**Repo:** `ov-suscripcion-automation`  
**Autor del reporte:** Generado por el agente con base en el estado actual del desarrollo

---

## 1. Contexto y rol del agente

Este repositorio implementa el **Step 6 (Code Agent)** del pipeline de orquestación end-to-end de OV Suscripciones:

```
Jira (webhook)
  → n8n (normalización)
  → Classifier Agent   — determina tipo de ticket
  → Enricher Agent     — expande a requisito técnico estructurado
  → QA Agent           — valida completitud y consistencia
  → Code Agent ◀ este repo
  → Azure Repos        — branch + Pull Request
  → n8n                — actualiza Jira ("En revisión" + link PR)
```

El agente recibe un **JSON payload estructurado** desde n8n (construido por los agentes anteriores) y produce:

1. Dos archivos Flyway con nombre canónico (`V{ts}__{TICKET}_{description}.xlsx` + `.java`)
2. Una rama `feature/...` en `ov-arizona-backend-ecuador` creada desde `origin/develop`
3. Un commit con exactamente esos 2 archivos
4. Push de la rama a Azure Repos (`origin`)

Lo que queda pendiente: abrir el Pull Request en Azure DevOps y notificar a n8n con el link del PR.

---

## 2. Estado actual del desarrollo

### 2.1 Flujo completo implementado

```
main.py (CLI o run-payload)
  │
  ├── build_description()       ← auto-deriva suffix del nombre Flyway
  ├── build_branch_name()       ← auto-deriva nombre de rama feature
  │
  ├── generator_ren_data.generate()   ← Tipo 1: baseticketMES.xlsx → FixedRenewalData.xlsx
  │     ├── _load_raw()               ← valida y normaliza, acumula todos los errores
  │     ├── _RowErrors                ← patrón de error acumulado (no fail-fast)
  │     └── ws.append()              ← bounds limpios para Flyway
  │
  ├── generator_rules.generate()     ← Tipo 2: raw.xlsx → RuleKit+RatingList+Entity+LOV.xlsx
  │
  ├── java_template.generate()       ← clase vacía que hereda LoadFromFileMigrationTask
  │
  └── placer.*
        ├── create_feature_branch()  ← fetch + checkout -b desde origin/develop
        ├── place()                  ← copia xlsx + java a rutas correctas del módulo
        └── git_add_commit_push()    ← valida par exacto → add → commit → push
              └── _validate_migration_pair()  ← 1 xlsx + 1 java, mismo stem, clase coincide
```

### 2.2 Tipos de migración soportados

| Tipo | Comando | Módulo backend | Descripción de negocio |
|---|---|---|---|
| **Tipo 1** | `ren-data` | `ams-policy` | Actualización mensual de vencimientos motor (Factor y chassis por póliza) |
| **Tipo 2** | `rules` | `ams-rule` | Actualización de reglas de tarificación (entidades como `VHPlanRules`, `VHPlanSetup`) |

### 2.3 Validaciones implementadas (Tipo 1)

`_load_raw` recorre el archivo completo antes de fallar, acumulando todos los errores:

| Condición | Error reportado |
|---|---|
| Chassis `None`, `""`, solo espacios | `Row N: Empty chassis number` |
| Factor `None` | `Row N (chassis '...'): Factor is empty` |
| Factor string ≠ `'No Renovar'` y no numérico | `Row N (chassis '...'): Factor must be numeric or 'No Renovar', got ...` |
| Chassis duplicado | `Row N (chassis '...'): Duplicate chassis — first seen at row M` |
| Columnas requeridas faltantes en header | Falla inmediata antes del bucle |

El operador ve **todos** los problemas del archivo en un solo mensaje de error, sin necesidad de re-ejecutar.

### 2.4 Invariante de migración

`_validate_migration_pair` en `placer.py` bloquea cualquier commit que no cumpla:

- Exactamente **2 archivos**: un `.xlsx` y un `.java`
- **Mismo nombre base** (stem idéntico)
- El nombre de la **clase Java** dentro del archivo coincide con el stem del archivo

Esta validación es la garantía final antes de tocar el repositorio destino.

### 2.5 Convención de nombres Flyway

```
V{YYYY_MM_DD_HH_MM_SS}__{TICKET_SANITIZADO}_{Description}
```

- Timestamp: momento exacto de generación (unicidad garantizada)
- Ticket: hyphens reemplazados por underscores (`ZNRX-67108` → `ZNRX_67108`) — Flyway rechaza guiones
- Descripción:
  - `ren-data` → `VH_ren_data_{mes_abr}_{year}` (ej. `VH_ren_data_ago_2026`)
  - `rules` → nombre de la entidad (ej. `VHPlanRules`)

### 2.6 Cobertura de tests

- `test_generator_ren_data.py` — estructura de sheets, headers, row count, Year/Month, No Renovar, LOV, bounds, sort, factor normalization, validación de errores acumulados
- `test_generator_rules.py` — auto-detección de versión, incremento, fórmulas como strings
- `test_description.py` — derivación de description y branch name (ren-data + rules, todos los meses)
- `test_payload.py` — modo payload, carga de config, derivación end-to-end
- `test_java_template.py` — template por módulo
- `run_migration_test.py` — runner e2e con archivos reales (4 meses: abril, mayo, junio, julio) → 17 checks por mes

---

## 3. Integración con n8n y Azure DevOps

### 3.1 Estado actual de la integración

| Paso del pipeline | Estado |
|---|---|
| Recibir JSON payload desde n8n | **Implementado** — subcomando `run-payload` |
| Derivar `description` automáticamente | **Implementado** — `src/description.py` |
| Generar archivos Flyway (xlsx + java) | **Implementado y testeado** |
| Crear feature branch desde `origin/develop` | **Implementado** — `placer.create_feature_branch()` |
| Commit + push a Azure Repos | **Implementado** — `placer.git_add_commit_push()` |
| Abrir Pull Request en Azure DevOps | **Pendiente** |
| Devolver PR link a n8n | **Pendiente** |
| n8n actualiza Jira con PR link + estado "En revisión" | Depende del paso anterior |

### 3.2 Contrato del payload JSON (n8n → Code Agent)

El Enricher/QA Agent construye este payload antes de invocar al Code Agent.

**Tipo 1 — ren-data:**
```json
{
  "command": "ren-data",
  "ticket": "ZNRX-67108",
  "input": "requirements/renovaciones/2026/agosto/baseticketAgosto2026.xlsx",
  "year": 2026,
  "month": 8,
  "commit": true
}
```

**Tipo 2 — rules:**
```json
{
  "command": "rules",
  "ticket": "ZNRX-67108",
  "input": "data/raw.xlsx",
  "entity": "VHPlanRules",
  "commit": true
}
```

Campos que **no van en el payload** (configuración local del servidor):
- `repo` — path al repo destino → en `config.json`
- `description` — auto-derivado en el agente
- `azure_pat` — PAT de Azure → en `config.json` (pendiente de uso)

### 3.3 Configuración local del servidor (`config.json`)

```json
{
  "repo": "../ov-arizona-backend-ecuador",
  "azure_pat": "PAT_GENERADO_EN_AZURE_DEVOPS"
}
```

Este archivo está en `.gitignore`. `config.json.example` está commiteado como referencia. El PAT se necesita para el paso pendiente de apertura del PR.

### 3.4 Pull Request — diseño pendiente

La función `open_pull_request()` a implementar en `src/placer.py` usará el SDK Python `azure-devops`:

```python
# Dependencia a instalar en el conda env:
# pip install azure-devops

from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

def open_pull_request(repo_root, branch_name, ticket_id, description, pat):
    creds = BasicAuthentication("", pat)
    connection = Connection(
        base_url="https://dev.azure.com/ZurichInsurance-EC", creds=creds
    )
    git_client = connection.clients.get_git_client()
    pr = {
        "source_ref_name": f"refs/heads/{branch_name}",
        "target_ref_name": "refs/heads/develop",
        "title": f"[{ticket_id}] {description}",
        "description": f"Migración Flyway generada automáticamente por Code Agent.",
    }
    result = git_client.create_pull_request(
        pr, "ov-arizona-backend-ecuador", project="Oficina-Virtual-ZEC"
    )
    return result.url  # URL del PR → se devuelve a n8n
```

El URL del PR resultante debe devolverse como respuesta del agente para que n8n lo escriba en el ticket Jira.

---

## 4. Rutas destino en `ov-arizona-backend-ecuador`

| Módulo | Archivo | Ruta |
|---|---|---|
| `ams-policy` | `.xlsx` | `ams-policy/flyway/src/main/resources/db/migration/` |
| `ams-policy` | `.java` | `ams-policy/flyway/src/main/java/eu/ncdc/arizona/policy/db/migration/` |
| `ams-rule` | `.xlsx` | `ams-rule/flyway/src/main/resources/db/migration/` |
| `ams-rule` | `.java` | `ams-rule/flyway/src/main/java/eu/ncdc/arizona/rule/db/migration/` |

---

## 5. Futuras implementaciones — otros tipos de solicitud

El agente está diseñado para soportar múltiples tipos de migración Flyway. A continuación se describen los candidatos naturales para extensión:

### 5.1 Tipo 3 — Actualización de LOV (`lov-update`)

**Descripción:** Los archivos `fixtures/lov_ams_policy.json` y `fixtures/lov_ams_rule.json` son snapshots estáticos del LOV del backend. Cuando el equipo de backend actualiza los valores del LOV, actualmente se deben actualizar manualmente.

**Automatización propuesta:**
- El agente reciría el archivo LOV actualizado desde el backend
- Regeneraría el `fixtures/lov_*.json` correspondiente
- Propagaría el cambio a las próximas migraciones automáticamente

**Módulos a modificar:** `fixtures/`, `generator_ren_data.py`, `generator_rules.py`

---

### 5.2 Tipo 4 — Nuevos módulos Flyway (`new-module`)

**Descripción:** El backend tiene múltiples módulos (`ams-accounting`, `ams-party`, `ams-claim`, etc.), cada uno con su propio directorio Flyway. Actualmente el agente solo soporta `ams-policy` y `ams-rule`.

**Automatización propuesta:** Añadir nuevas entradas a los diccionarios `_MODULE_JAVA_PATH`, `_MODULE_RESOURCES_PATH` en `src/placer.py` y `_MODULE_PACKAGE` en `src/java_template.py`. El patrón de generación es idéntico — solo cambia el módulo destino.

**Módulos a modificar:** `src/placer.py`, `src/java_template.py`, `CLAUDE.md`

---

### 5.3 Tipo 5 — Carga de catálogos parametrizados (`catalog-load`)

**Descripción:** Algunos tickets de Jira solicitan cargar catálogos de datos (coberturas, planes, tasas) que no son renovaciones motor ni reglas de tarificación, pero siguen el mismo patrón Flyway (xlsx + java).

**Automatización propuesta:** Un nuevo comando `catalog-load` con su propio generador `generator_catalog.py`. El generador leería un Excel de negocio con formato libre y lo transformaría al esquema que espera la entidad destino.

**Requiere:** Definir el esquema de cada tipo de catálogo (columnas, validaciones) en el payload o en un archivo de configuración de esquemas.

---

### 5.4 Tipo 6 — Actualización de configuración Java (`java-patch`)

**Descripción:** Algunos tickets no requieren migración de datos sino modificar directamente un archivo `.java` existente (por ejemplo, actualizar una constante, cambiar un valor de configuración en un `@Bean`, o activar/desactivar una feature flag).

**Automatización propuesta:** El agente reciría el archivo destino y el cambio estructurado (campo → valor nuevo), aplicaría el patch, y generaría el commit. Requiere parsing básico de Java (posiblemente con regex sobre patterns conocidos, sin AST completo).

**Riesgo:** Mayor superficie de error que los cambios Excel-only. Requiere validación más robusta y posiblemente revisión humana obligatoria antes del merge.

---

### 5.5 Tipo 7 — Rollback de migración (`rollback`)

**Descripción:** Cuando una migración genera un problema en producción, actualmente el rollback es manual. Flyway no soporta rollback nativo en la versión usada (5.2.4), por lo que se requiere una migración inversa.

**Automatización propuesta:** Dado el nombre de un archivo de migración ya commiteado, el agente generaría una migración de reversión (xlsx vacío o con datos de restore + clase java correspondiente).

**Requiere:** Acceso a los archivos de migración anteriores en el repo (ya disponible vía `placer._MODULE_RESOURCES_PATH`) y una convención para identificar la migración inversa.

---

### 5.6 Resumen de roadmap

| Tipo | Comando propuesto | Prioridad estimada | Complejidad |
|---|---|---|---|
| PR en Azure DevOps | (integrado en `--commit`) | **Alta — inmediata** | Baja |
| Nuevos módulos Flyway | `new-module` o extensión de tipos 1/2 | Media | Muy baja |
| Actualización de LOV | `lov-update` | Media | Baja |
| Catálogos parametrizados | `catalog-load` | Media-baja | Media |
| Patch de Java | `java-patch` | Baja | Alta |
| Rollback de migración | `rollback` | Baja | Media |

---

## 6. Principios de diseño del agente

Estos principios guían todas las decisiones de implementación actuales y futuras:

1. **Fail visible, no silencioso.** Todo error de validación se acumula y se reporta en un solo mensaje con contexto de fila — el operador nunca debe re-ejecutar para descubrir el siguiente error.

2. **Exactamente 2 archivos por migración, siempre.** La regla `_validate_migration_pair` es el último guardián antes del commit. Nunca se relaja.

3. **Derivación determinista.** `description` y `branch_name` se derivan desde los parámetros de negocio (mes, año, entidad). No hay campos de libre texto en el payload que puedan generar inconsistencias.

4. **Separación de credenciales.** El PAT de Azure y el path al repo nunca viajan en el payload — viven en `config.json` local del servidor. El payload es stateless respecto al entorno de ejecución.

5. **El commit message preserva trazabilidad Jira.** El ticket original (`ZNRX-67108`, con guiones) se usa en el mensaje de commit. El ticket sanitizado (`ZNRX_67108`) se usa solo en nombres de archivo y clase.

6. **Incrementalidad.** Cada tipo de migración nuevo sigue el mismo patrón `generator_*.py` + entradas en los dicts de `placer.py`. No se introducen abstracciones hasta que hay al menos 3 tipos que las justifiquen.
