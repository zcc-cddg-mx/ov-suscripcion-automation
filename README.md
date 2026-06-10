# ov-suscripcion-automation

Herramienta CLI para automatizar la generación de migraciones Flyway de solicitudes de suscripción en OV.

Cada solicitud produce exactamente dos archivos con el mismo nombre base:
- `V{TIMESTAMP}__{TICKET}_{Descripcion}.xlsx` — datos para Apache POI
- `V{TIMESTAMP}__{TICKET}_{Descripcion}.java` — clase que extiende `LoadFromFileMigrationTask`

## Tipos soportados

| Tipo | Comando | Módulo destino |
|---|---|---|
| Vencimientos motor (`VH_ren_data`) | `ren-data` | `ams-policy` |
| Reglas de tarificación (`VHPlanRules`, etc.) | `rules` | `ams-rule` |

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

### Tipo 1 — Vencimientos motor

```bash
python main.py ren-data \
  --input data/raw_agosto.xlsx \
  --ticket INC23999999 \
  --description VH_ren_data_aug \
  --repo /path/to/ov-arizona-backend-ecuador \
  [--commit]
```

El Excel raw debe tener columnas (nombres en español o inglés):
`chassis / year / month / factor / sum insured / renewal blocked`

### Tipo 2 — Reglas de tarificación

```bash
python main.py rules \
  --input data/raw_rules.xlsx \
  --ticket RITM2500000 \
  --entity VHPlanRules \
  --repo /path/to/ov-arizona-backend-ecuador \
  [--commit]
```

El Excel raw debe tener las columnas de la entidad (sin ID ni Rating list — se agregan automáticamente).

La versión se lee del último archivo de migración existente en el repo y se incrementa en 1.

## Estructura del proyecto

```
main.py                    # Punto de entrada CLI
src/
  generator_ren_data.py    # Generador Tipo 1
  generator_rules.py       # Generador Tipo 2
  java_template.py         # Genera la clase Java
  placer.py                # Copia archivos al repo y hace git commit
fixtures/
  VHPlanRules_reference.xlsx  # Excel de referencia ams-rule
  VH_ren_data_reference.xlsx  # Excel de referencia ams-policy
  lov_ams_rule.json           # LOV estático ams-rule
  lov_ams_policy.json         # LOV estático ams-policy
tests/
  test_generator_ren_data.py
  test_generator_rules.py
  test_java_template.py
```

## Tests

```bash
pip install pytest
python -m pytest tests/ -v
```
