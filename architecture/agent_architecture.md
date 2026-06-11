# Code Agent — Arquitectura local

## Rol en el pipeline global

Este agente es el **Step 4** del pipeline de orquestación end-to-end:

```
Jira (webhook)
  → n8n (normalización)
  → Classifier + Enricher Agent  — clasifica el ticket y construye requisito técnico estructurado
  → Code Agent ◀ este repo
  → Azure Repos (Branch + PR)
  → n8n (actualiza Jira → "En revisión" + link PR)
  → QA Agent  — valida el PR (diff real, no el requisito abstracto)
  → PR Aprobado / Observaciones → Jira + comentarios en PR
```

**Cambio arquitectónico clave:** el QA Agent actúa *después* del PR, no antes del Code Agent. Valida el diff real en Azure Repos. El Code Agent no espera validación previa — recibe el requisito enriquecido y actúa directamente.

**Input:** JSON payload estructurado (desde n8n) o CLI manual — ticket ID, tipo de migración, archivo de negocio, año/mes o entity. El campo `description` se auto-deriva; el path al repo viene de `config.json` local.  
**Output:** dos archivos Flyway (`.xlsx` + `.java`) con nombre `V{YYYY_MM_DD_HH_MM_SS}__{TICKET}_{Description}`, colocados en el repo destino como PR hacia `developer`.

---

## Estructura del proyecto

```
ov-suscripcion-automation/
├── main.py                        # CLI entry point (subcomandos: ren-data, rules, run-payload)
├── config.json                    # Config local del agente — path al repo destino (en .gitignore)
├── config.json.example            # Plantilla de configuración (commiteada)
├── src/
│   ├── generator_ren_data.py      # Generador Tipo 1 — vencimientos motor (ams-policy)
│   ├── generator_rules.py         # Generador Tipo 2 — reglas de tarificación (ams-rule)
│   ├── config.py                  # Carga config.json local (load_config)
│   ├── description.py             # Auto-deriva description del nombre de archivo (build_description)
│   ├── java_template.py           # Template .java por módulo
│   └── placer.py                  # Copia archivos al repo destino, git commit opcional
├── fixtures/
│   ├── lov_ams_policy.json        # LOV estático ams-policy (289 filas)
│   └── lov_ams_rule.json          # LOV estático ams-rule (25 filas)
├── tests/
│   ├── test_generator_ren_data.py # 30 tests — estructura, validación, factor, sort
│   ├── test_generator_rules.py    # Tests generador tipo 2
│   ├── test_java_template.py      # Tests template Java
│   ├── test_description.py        # Tests derivación automática de description (9 tests)
│   ├── test_payload.py            # Tests modo payload y config loading (8 tests)
│   └── run_migration_test.py      # Runner e2e con archivos reales → tests/migrations/
├── requirements/
│   └── renovaciones/YYYY/MES/     # Archivos de entrada de negocio (baseticketMES.xlsx)
└── architecture/
    ├── info.md                    # Diagrama pipeline global
    └── agent_architecture.md      # Este documento
```

---

## Tipos de migración soportados

| Tipo | CLI | Módulo destino | Hoja principal |
|---|---|---|---|
| Vencimientos motor | `ren-data` | `ams-policy` | `FixedRenewalData` + `LOV` |
| Reglas de tarificación | `rules` | `ams-rule` | `RuleKit` + `RatingList` + `{Entity}` + `LOV` |

---

## Flujo interno — Tipo 1 (`ren-data`)

```
main.py (CLI)
  │  --input, --ticket, --year, --month, --repo, [--commit]
  ▼
generator_ren_data.generate(raw_input, output, year, month)
  │
  ├─ _load_raw(path, year, month)
  │    ├─ Carga hoja activa del Excel de negocio
  │    ├─ Normaliza headers (aliases ES/EN → canonical)
  │    ├─ Valida columnas requeridas en header (falla inmediata)
  │    ├─ Por cada fila no-vacía:
  │    │    ├─ _validate_chassis() → acumula error si vacío/None
  │    │    └─ _validate_and_normalize_factor() → acumula error si inválido
  │    ├─ Post-bucle: detecta chassis duplicados
  │    ├─ _RowErrors.raise_if_any() → lanza ValueError con lista completa
  │    └─ Ordena: numérico ASC + 'No Renovar' al final
  │
  ├─ Workbook openpyxl:
  │    ├─ Hoja "LOV"             ← fixtures/lov_ams_policy.json (289 filas estáticas)
  │    └─ Hoja "FixedRenewalData" ← ws.append() secuencial (bounds limpios para Flyway)
  │
  └─ Guarda .xlsx en tmp/
  
java_template.generate(base_name, "ams-policy")
  └─ Genera clase Java vacía que extiende LoadFromFileMigrationTask

placer.place(xlsx, java, base_name, module, repo_root)
  └─ Copia ambos archivos a las rutas correctas del repo ov-arizona-backend-ecuador

placer.git_add_commit_push(...)    ← solo si --commit (valida par, commit, push a origin)
```

---

## Flujo interno — Tipo 2 (`rules`)

```
main.py (CLI)
  │  --input, --ticket, --entity, --repo, [--commit]
  ▼
generator_rules.generate(raw_input, output, entity_name, resources_path)
  │
  ├─ Detecta versión actual: busca último *_{EntityName}.xlsx en resources_path
  ├─ Lee fila NEW → incrementa versión en +1
  │
  └─ Workbook openpyxl:
       ├─ Hoja "RuleKit"        ← solo headers
       ├─ Hoja "RatingList"     ← filas OLD/NEW con =TODAY() como string
       ├─ Hoja "{EntityName}"   ← columnas ID + RatingList prepended + datos del input
       └─ Hoja "LOV"            ← fixtures/lov_ams_rule.json (25 filas estáticas)
```

---

## Validación de datos — Tipo 1

`_load_raw` acumula **todos** los errores antes de fallar (patrón `_RowErrors`):

| Error | Condición | Mensaje |
|---|---|---|
| Chassis vacío | `None`, `""`, solo espacios | `Row N: Empty chassis number` |
| Factor vacío | `None` | `Row N (chassis '...'): Factor is empty` |
| Factor inválido | string ≠ `'No Renovar'` | `Row N (chassis '...'): Factor must be numeric or 'No Renovar', got ...` |
| Chassis duplicado | mismo valor en ≥2 filas | `Row N (chassis '...'): Duplicate chassis — first seen at row M` |
| Columnas faltantes | header sin `CHASIS` o `TASA FINAL` | falla inmediata (antes del bucle) |

Formato del error acumulado:
```
Validation failed: 3 error(s) in input file:
  • Row 3: Empty chassis number
  • Row 4 (chassis 'C003'): Factor must be numeric or 'No Renovar', got 'INVALIDO' (str)
  • Row 6 (chassis 'C001'): Duplicate chassis — first seen at row 2
```

---

## Convención de nombres Flyway

```
V{YYYY_MM_DD_HH_MM_SS}__{TICKET_ID}_{Description}
```

Ejemplo: `V2026_06_10_14_30_00__INC23703493_VH_ren_data_jul`

Cada migración produce exactamente dos archivos con el mismo nombre base:
- `.xlsx` → datos en el módulo `flyway/src/main/resources/db/migration/`
- `.java` → clase vacía en `flyway/src/main/java/eu/ncdc/arizona/{module}/db/migration/`

---

## Rutas destino en `ov-arizona-backend-ecuador`

| Módulo | xlsx | java |
|---|---|---|
| `ams-policy` | `ams-policy/flyway/src/main/resources/db/migration/` | `ams-policy/flyway/src/main/java/eu/ncdc/arizona/policy/db/migration/` |
| `ams-rule` | `ams-rule/flyway/src/main/resources/db/migration/` | `ams-rule/flyway/src/main/java/eu/ncdc/arizona/rule/db/migration/` |

---

## Payload JSON (contrato con n8n)

El subcomando `run-payload` recibe un archivo JSON que el Enricher/QA Agent construye a partir del ticket Jira. El `repo` no viaja en el payload — se lee de `config.json` local del servidor.

**Tipo 1 — ren-data:**
```json
{
  "command": "ren-data",
  "ticket": "ZNRX-67108",
  "input": "requirements/renovaciones/2026/agosto/baseticketAgosto2026.xlsx",
  "year": 2026,
  "month": 8,
  "commit": false
}
```

**Tipo 2 — rules:**
```json
{
  "command": "rules",
  "ticket": "ZNRX-67108",
  "input": "data/raw.xlsx",
  "entity": "VHPlanRules",
  "commit": false
}
```

**`description` auto-derivada (no va en el payload):**
- `ren-data` → `VH_ren_data_{mes_abrev}_{year}` (ej. `VH_ren_data_ago_2026`)
- `rules`    → `{entity}` (ej. `VHPlanRules`)

**`config.json` (fijo en el servidor, en `.gitignore`):**
```json
{ "repo": "../ov-arizona-backend-ecuador" }
```

---

## Estrategia de ramas

Por cada ejecución con `--commit` el agente produce **2 ramas**:

```
feature/{ticket}_{suffix}
  └── cortada de origin/developer
  └── 2 archivos (xlsx + java) + commit + push
        │
        ├──── PR ──► developer  ◄── alcance del agente
        │
{base_name}_developer_auxiliar
  └── cortada limpia de origin/developer
  └── mismos 2 archivos copiados con 'git show <feature>:<path>'
      (sin merge — cero conflictos posibles)
  └── commit + push a origin
        │
        └──── PR ──► developer  ◄── rama candidata al PR

developer  ──► PR ──► main  (producción — proceso manual)
```

**Por qué `git show` en lugar de merge:** el merge podría traer cambios de `developer` no relacionados con la migración. Con `git show` la rama auxiliar contiene exactamente `developer` + los 2 archivos nuevos — sin sorpresas.

---

## Estado de integración con el pipeline

| Paso | Scope | Estado |
|---|---|---|
| Recibir payload JSON estructurado desde n8n | Agente | **Implementado** — `run-payload` + `src/config.py` |
| Derivar `description` automáticamente | Agente | **Implementado** — `src/description.py` |
| Generar archivos Flyway | Agente | **Implementado y testeado** |
| Crear feature branch desde `origin/developer` + commit + push | Agente | **Implementado** — `placer.create_feature_branch` + `git_add_commit_push` |
| Crear rama auxiliar `{base_name}_developer_auxiliar` + push | Agente | **Implementado** — `placer.create_auxiliary_branch` (git show, sin merge) |
| Validar par exacto (1 xlsx + 1 java, mismo nombre, clase coincide) | Agente | **Implementado** — `_validate_migration_pair` en `placer.py` |
| Abrir PR: `{base_name}_developer_auxiliar` → `developer` | Agente | **Pendiente** — SDK `azure-devops` (pip), PAT en `config.json` |
| Notificar a n8n (PR link) | Agente | **Pendiente** |
| PR `developer` → `main` (producción) | Release manual | Fuera del alcance del agente |
