"""
Generator for migration type 2: rating rules (VHPlanRules, VHPlanSetup, etc.) in ams-rule.

Reads the current version from the last matching migration in the target repo,
increments it, and produces a Flyway-ready Excel with sheets:
  RuleKit | RatingList | <EntityName> | LOV
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

_FIXTURES = Path(__file__).parent.parent / "fixtures"
_LOV_FILE = _FIXTURES / "lov_ams_rule.json"

_RULEKIT_HEADERS = ["ID", "Code", "Name", "Description", "Version", "State"]

_RATINGLIST_HEADERS = [
    "ID", "Rule kit", "Type", "Code", "Name", "Description",
    "Selector", "Selector type", "Version", "Valid from", "Valid to", "State",
]


def _entity_to_code(entity_name: str) -> str:
    """VHPlanRules → VH_PLAN_RULES.

    Inserts _ between:
    - a lowercase letter and an uppercase letter  (Plan → _Plan)
    - a run of uppercase letters and the start of the next word (VHP → VH_P)
    """
    # Between a run of uppercase and an upcoming uppercase+lowercase  (e.g. VHPlan → VH_Plan)
    result = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", entity_name)
    # Between a lowercase letter and an uppercase letter (e.g. PlanRules → Plan_Rules)
    result = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", result)
    return result.upper()


def _find_last_migration(repo_resources_path: Path, entity_name: str) -> Path | None:
    """Return the most recent xlsx for *entity_name* in the migration resources directory."""
    pattern = f"*_{entity_name}.xlsx"
    candidates = sorted(repo_resources_path.glob(pattern))
    return candidates[-1] if candidates else None


def _read_current_version(xlsx_path: Path) -> tuple[int, datetime | None]:
    """
    From a previous migration xlsx, read the NEW row in RatingList.
    Returns (version, valid_from_date).
    """
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb["RatingList"]
    rows = list(ws.iter_rows(values_only=True))
    headers = rows[0]
    id_idx = list(headers).index("ID")
    ver_idx = list(headers).index("Version")
    from_idx = list(headers).index("Valid from")

    for row in rows[1:]:
        if row[id_idx] == "NEW":
            version = row[ver_idx]
            valid_from = row[from_idx]
            if isinstance(valid_from, str):
                # formula string — use today as fallback
                valid_from = None
            return int(version), valid_from

    raise ValueError(f"No NEW row found in RatingList of {xlsx_path}")


def _load_raw_rules(path: Path) -> tuple[list[str], list[list[Any]]]:
    """Return (headers, data_rows) from the raw input Excel."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError(f"Empty workbook: {path}")
    headers = [str(c) if c is not None else "" for c in rows[0]]
    data = [list(row) for row in rows[1:] if any(c is not None for c in row)]
    return headers, data


def _write_rulekit(ws: Worksheet) -> None:
    ws.append(_RULEKIT_HEADERS)


def _write_ratinglist(
    ws: Worksheet,
    entity_code: str,
    entity_name: str,
    old_version: int,
    old_valid_from: datetime | None,
) -> None:
    ws.append(_RATINGLIST_HEADERS)
    new_version = old_version + 1

    old_from_val: Any = old_valid_from if old_valid_from else datetime(2024, 1, 1)

    ws.append([
        "OLD", None, "Global", entity_code, entity_name, entity_name,
        None, "None", old_version, old_from_val, "=TODAY()-(0.5/24)", "Draft",
    ])
    ws.append([
        "NEW", None, "Global", entity_code, entity_name, entity_name,
        None, "None", new_version, "=TODAY()", None, "Draft",
    ])


def _write_entity_sheet(
    ws: Worksheet,
    raw_headers: list[str],
    raw_data: list[list[Any]],
) -> None:
    """Write headers then data rows, prepending None (ID) and 'NEW' (Rating list)."""
    full_headers = ["ID", "Rating list"] + raw_headers
    ws.append(full_headers)
    for row in raw_data:
        ws.append([None, "NEW"] + row)


def _write_lov(ws: Worksheet) -> None:
    lov_data: list[list[Any]] = json.loads(_LOV_FILE.read_text(encoding="utf-8"))
    for row in lov_data:
        ws.append(row)


def generate(
    raw_input: Path,
    output: Path,
    entity_name: str,
    repo_resources_path: Path,
) -> None:
    """
    Transform *raw_input* into a Flyway-ready rules Excel at *output*.

    *entity_name*: e.g. "VHPlanRules"
    *repo_resources_path*: path to ams-rule/flyway/src/main/resources/db/migration/
    """
    entity_code = _entity_to_code(entity_name)
    raw_headers, raw_data = _load_raw_rules(raw_input)

    last_migration = _find_last_migration(repo_resources_path, entity_name)
    if last_migration is None:
        raise FileNotFoundError(
            f"No previous migration found for {entity_name} in {repo_resources_path}"
        )
    current_version, valid_from = _read_current_version(last_migration)

    wb = Workbook()

    ws_rulekit = wb.active
    ws_rulekit.title = "RuleKit"
    _write_rulekit(ws_rulekit)

    ws_rating = wb.create_sheet("RatingList")
    _write_ratinglist(ws_rating, entity_code, entity_name, current_version, valid_from)

    ws_entity = wb.create_sheet(entity_name)
    _write_entity_sheet(ws_entity, raw_headers, raw_data)

    ws_lov = wb.create_sheet("LOV")
    _write_lov(ws_lov)

    wb.save(output)
