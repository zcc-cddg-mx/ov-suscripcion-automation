# VHDriversAge — Plan end-to-end

## Estado del componente

| Componente | Archivo | Estado |
|---|---|---|
| Loader + validación | `src/generator_rules.py` — `_load_cotizador_drivers_age()` | ✅ |
| Transformación (80+, sentinel, P.JURIDICA) | `src/generator_rules.py` | ✅ |
| Tests unitarios (21/21) | `tests/test_generator_rules.py::TestCotizadorDriversAge` | ✅ |
| Runner e2e (12 checks) | `tests/run_rules_test.py` | ✅ |
| CLI `cmd_rules()` | `main.py` | ✅ |
| API — `entity` requerido para rules | `app.py` | ✅ |
| Documentación pipeline | `fixtures/rules/drivers-age/MAPPING.md` | ✅ |
| `description` fluye correctamente desde payload | `main.py:124` | ✅ |
| Campo `password` fluye HTTP → generador | `app.py` + `main.py` | ✅ |

---

## Flujo completo (punta a punta)

```
negocio entrega:
  Cotizador_MotorIndividualV25.xlsx  (contraseña: BUSINESS_EXCEL_PASSWORD)

        │  CLI                             │  HTTP API (n8n)
        ▼                                  ▼
  main.py rules                      POST /run  (multipart)
    --input cotizador.xlsx              file=cotizador.xlsx
    --entity VHDriversAge               command=rules
    --ticket RITM-XXXXX                 entity=VHDriversAge
    --repo ../ov-arizona-backend-ecuador ticket=RITM-XXXXX
    [--commit]                          commit=true

        └──────────────┬────────────────────┘
                       ▼
              run_payload(payload)
                       │
                       ▼
              cmd_rules(ns)
                ├─ generator_rules.generate()
                │    └─ _load_cotizador_drivers_age()
                │         ├─ decrypt con msoffcrypto (password)
                │         ├─ hoja Relatividades → tabla EDAD_INPUT
                │         ├─ 17–79 → from=to=int(age)
                │         ├─ 80+   → from=80, to=998
                │         ├─ P.JURIDICA → skip
                │         └─ sentinel   → (999, 999, all=1)
                │    └─ produce: RuleKit / RatingList / VHDriversAge / LOV
                │
                ├─ java_template.generate()
                │    └─ package eu.ncdc.arizona.rule.db.migration
                │
                ├─ placer.create_feature_branch()
                │    └─ feature/RITM_XXXXX_VH_Drivers_Age  (desde origin/developer)
                │
                ├─ placer.place()
                │    ├─ xlsx → ams-rule/flyway/.../db/migration/
                │    └─ java → ams-rule/flyway/.../java/.../rule/db/migration/
                │
                ├─ build_check.verify()  (si compile=true)
                │    └─ gradle :ams-rule:flyway:compileJava
                │
                ├─ placer.git_add_commit_push()
                │    └─ commit "[RITM-XXXXX] VHDriversAge" → push feature branch
                │
                └─ placer.create_auxiliary_branch()
                     └─ feature/RITM_XXXXX_VH_Drivers_Age_developer_auxiliar

        ▼
  Respuesta a n8n:
  {
    "branch":       "feature/RITM_XXXXX_VH_Drivers_Age",
    "aux_branch":   "feature/RITM_XXXXX_VH_Drivers_Age_developer_auxiliar",
    "commit_id":    "abc123...",
    "build_status": "success",
    "repo":         "ov-arizona-backend-ecuador"
  }

        ▼
  n8n crea PR: feature/... → developer
  (developer → main es proceso manual separado)
```

---

## Pasos de verificación

### 1. Tests unitarios
```bash
BUSINESS_EXCEL_PASSWORD=Motor2023* conda run -n ov-suscripcion \
  python -m pytest tests/test_generator_rules.py -v
# Esperado: 21/21 PASSED
```

### 2. Runner e2e (12 checks, comparación vs referencia)
```bash
BUSINESS_EXCEL_PASSWORD=Motor2023* conda run -n ov-suscripcion \
  python tests/run_rules_test.py --entity VHDriversAge
# Esperado: ALL CHECKS PASSED → tests/migrations/V..._VHDriversAge.xlsx
# Nota: si VHDriversAge_reference.xlsx no está en disco, el check 12 se salta
```

### 3. CLI dry-run (sin commit)
```bash
BUSINESS_EXCEL_PASSWORD=Motor2023* conda run -n ov-suscripcion \
  python main.py rules \
    --input "fixtures/rules/business-reference/Cotizador_MotorIndividualV25.xlsx" \
    --entity VHDriversAge \
    --ticket TEST99999 \
    --repo ../ov-arizona-backend-ecuador
# Verifica: archivos en ams-rule/.../db/migration/, sin branch creado
```

### 4. CLI --commit
```bash
BUSINESS_EXCEL_PASSWORD=Motor2023* conda run -n ov-suscripcion \
  python main.py rules \
    --input "fixtures/rules/business-reference/Cotizador_MotorIndividualV25.xlsx" \
    --entity VHDriversAge \
    --ticket RITM-TEST999 \
    --repo ../ov-arizona-backend-ecuador \
    --commit
# Verifica: feature/RITM_TEST999_VH_Drivers_Age + auxiliar en origin
```

### 5. Suite completa
```bash
TASKS_DB=/tmp/test_tasks.db BUSINESS_EXCEL_PASSWORD=Motor2023* conda run -n ov-suscripcion \
  python -m pytest tests/ -v --ignore=tests/test_build_check.py
# Esperado: 94/94 PASSED
```

---

## Archivos en git

| Archivo | En git | Descripción |
|---|---|---|
| `MAPPING.md` | ✅ | Transformación paso a paso: fuente → salida |
| `PLAN.md` | ✅ | Este archivo — flujo completo y verificación |
| `VHDriversAge_reference.java` | ✅ | Plantilla clase Java (vacía) |
| `VHDriversAge_reference.xlsx` | ❌ | Migración Flyway de referencia — distribuir por separado |
