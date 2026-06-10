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
python main.py ren-data --input requirements/renovaciones/2026/agosto/baseticketAgosto2026.xlsx --ticket INC99999 --description VH_ren_data_ago --year 2026 --month 8 --repo ../ov-arizona-backend-ecuador
python main.py rules    --input data/raw.xlsx --ticket RITM9999 --entity VHPlanRules --repo ../ov-arizona-backend-ecuador

# Add --commit to auto-commit generated files to the target repo
python main.py rules --input data/raw.xlsx --ticket RITM9999 --entity VHPlanRules --repo ../ov-arizona-backend-ecuador --commit
```

## What this tool does

This is the **Code Agent** (Step 6) of a larger end-to-end orchestration pipeline: `Jira → n8n → Classifier → Enricher → QA → Code Agent → Azure Repos → Jira`. See `architecture/agent_architecture.md` for the full picture.

Automates Flyway migration requests for OV subscriptions. Each migration requires exactly two files with matching names — one `.xlsx` (data) and one `.java` (empty class that inherits `LoadFromFileMigrationTask`). The tool generates both and places them in the correct paths of the `ov-arizona-backend-ecuador` repo.

Naming convention: `V{YYYY_MM_DD_HH_MM_SS}__{TICKET_ID}_{Description}`

## Migration types

### Tipo 1 — `ren-data` (vencimientos motor)
- **Target module:** `ams-policy`
- **Input:** Real files from negocio: `requirements/renovaciones/YYYY/MES/baseticketMES.xlsx`
  - Columns: `CHASIS`, `TASA FINAL`, `PLACAS` (+ empty trailing columns/rows — filtered automatically)
  - `Year` and `Month` are not in the file — pass via `--year` and `--month`
  - `TASA FINAL = 'No Renovar'` (case-insensitive) is a **business rule** — rows are **included** in output with `Factor='No Renovar'` and `Renewal blocked='Yes'` (~2–18 per month)
  - ~1300–1600 valid rows per file; ~2000+ empty trailing rows are normal
- **Row validation (all errors accumulated before failing):** `_load_raw` collects every error in the file and raises a single `ValueError` at the end with a bulleted list — operators see all problems in one pass:
  - Chassis `None`, empty string, or whitespace → `"Row N: Empty chassis number"`
  - Factor `None` → `"Row N (chassis '...'): Factor is empty"` (distinct from invalid value)
  - Factor invalid string → `"Row N (chassis '...'): Factor must be numeric or 'No Renovar', got ..."`
  - Duplicate chassis → `"Row N (chassis '...'): Duplicate chassis — first seen at row M"`
  - Missing required columns in header → immediate fail before row loop
- **Factor validation and normalization:**
  - Numeric ≤8 decimal places → written as-is
  - Numeric >8 decimal places → `round(value, 8)` (business files commonly carry 10–18 decimals from calculation artifacts)
  - `'No Renovar'` string → pass-through
  - Any other non-numeric value → accumulated as error
  - Decimal counting uses `Decimal(str(v)).normalize().as_tuple()` (avoids float binary noise)
- **Output row order:** numeric factors sorted ascending, `'No Renovar'` rows grouped at end (matches production reference)
- **Table bounds (Flyway safety):** `ws.append()` sequential writes guarantee `max_row = 1 + N_records`, `max_column = 7`, zero empty rows inside the table — dynamic based on baseTicket row count
- **Output sheets:** `LOV` (static, 289 rows from `fixtures/lov_ams_policy.json`) + `FixedRenewalData`

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

## End-to-end runner (ren-data)

`tests/run_migration_test.py` generates real migration files into `tests/migrations/` and runs 17 checks:

```bash
# Run with default month (julio)
python tests/run_migration_test.py

# Run specific month
python tests/run_migration_test.py --month abril
python tests/run_migration_test.py --month julio --ticket INC23703493
```

Available months: `abril`, `mayo`, `junio`, `julio`. Add new months to `_MONTHS` dict in the runner.

The 17 checks cover: sheets order, headers, row count, Year/Month injection, ID=None, No Renovar→blocked=Yes, normal→blocked=No, LOV=289 rows, no empty rows inside table, column count=7, numeric factors sorted ASC, No Renovar at end, plus 4 reference comparisons (row count, chassis set, Factor values, No Renovar count) when a `reference_xlsx` is configured.
