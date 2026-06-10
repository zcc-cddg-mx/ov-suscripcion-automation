# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Conda environment

All commands must run inside the `ov-suscripcion` conda environment:

```bash
conda activate ov-suscripcion
```

## Common commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_generator_ren_data.py -v

# Run a single test
python -m pytest tests/test_generator_rules.py::TestGeneratorRules::test_ratinglist_version_incremented -v

# Run the CLI (dry-run, no commit)
python main.py ren-data --input data/raw.xlsx --ticket INC99999 --description VH_ren_data_aug --repo ../ov-arizona-backend-ecuador
python main.py rules    --input data/raw.xlsx --ticket RITM9999 --entity VHPlanRules --repo ../ov-arizona-backend-ecuador

# Add --commit to auto-commit generated files to the target repo
python main.py rules --input data/raw.xlsx --ticket RITM9999 --entity VHPlanRules --repo ../ov-arizona-backend-ecuador --commit
```

## What this tool does

Automates Flyway migration requests for OV subscriptions. Each migration requires exactly two files with matching names — one `.xlsx` (data) and one `.java` (empty class that inherits `LoadFromFileMigrationTask`). The tool generates both and places them in the correct paths of the `ov-arizona-backend-ecuador` repo.

Naming convention: `V{YYYY_MM_DD_HH_MM_SS}__{TICKET_ID}_{Description}`

## Migration types

### Tipo 1 — `ren-data` (vencimientos motor)
- **Target module:** `ams-policy`
- **Input:** Raw business Excel with chassis/year/month/factor columns (Spanish or English names accepted — see `_COL_ALIASES` in `src/generator_ren_data.py`)
- **Output sheets:** `LOV` (static, 289 rows from `fixtures/lov_ams_policy.json`) + `FixedRenewalData`
- **Real requirements files** are stored under `requirements/renovaciones/YYYY/MES/` and have columns: `CHASIS`, `TASA FINAL`, `PLACAS`. `CHASIS` → `Chassis number`, `TASA FINAL` → `Factor`. These files lack `Year` and `Month` columns — they must be added manually before using as `--input`, or the generator extended to accept year/month as CLI arguments.

### Tipo 2 — `rules` (reglas de tarificación)
- **Target module:** `ams-rule`
- **Input:** Raw Excel with rule columns (no ID or Rating list — these are prepended automatically)
- **Output sheets:** `RuleKit` (headers only) + `RatingList` (OLD/NEW version rows) + `{EntityName}` + `LOV` (static, 25 rows from `fixtures/lov_ams_rule.json`)
- **Version auto-detection:** reads the last `*_{EntityName}.xlsx` in the repo's migration directory, takes the NEW row version, and increments it by 1
- **Formulas written as strings:** `=TODAY()` and `=TODAY()-(0.5/24)` are stored as formula strings in openpyxl (not evaluated values)

## Target repo paths

| Module | xlsx destination | java destination |
|---|---|---|
| `ams-rule` | `ams-rule/flyway/src/main/resources/db/migration/` | `ams-rule/flyway/src/main/java/eu/ncdc/arizona/rule/db/migration/` |
| `ams-policy` | `ams-policy/flyway/src/main/resources/db/migration/` | `ams-policy/flyway/src/main/java/eu/ncdc/arizona/policy/db/migration/` |

Adding a new module requires updating both `_MODULE_JAVA_PATH` and `_MODULE_RESOURCES_PATH` dicts in `src/placer.py`, and `_MODULE_PACKAGE` in `src/java_template.py`.

## Fixtures

`fixtures/lov_ams_policy.json` and `fixtures/lov_ams_rule.json` are static snapshots of the LOV sheets from the reference Excel files. They must be updated if the LOV content changes in the backend repo. The reference Excel files are kept alongside them for comparison.

## Tests

Tests in `tests/test_generator_rules.py` resolve `_AMS_RULE_RESOURCES` relative to the project root pointing to `../ov-arizona-backend-ecuador/ams-rule/flyway/src/main/resources/db/migration/`. The target repo must be present at that path for the rules generator tests to pass.
