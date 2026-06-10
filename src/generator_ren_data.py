"""
Generator for migration type 1: VH_ren_data (ams-policy).

Transforms a raw business Excel (chassis / year / month / factor / sum_insured columns)
into the Flyway-ready Excel with sheets: LOV, FixedRenewalData.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

_FIXTURES = Path(__file__).parent.parent / "fixtures"
_LOV_FILE = _FIXTURES / "lov_ams_policy.json"

# Accepted column name aliases → canonical name
_COL_ALIASES: dict[str, str] = {
    "chassis": "Chassis number",
    "chassis number": "Chassis number",
    "chasis": "Chassis number",
    "year": "Year",
    "año": "Year",
    "anio": "Year",
    "month": "Month",
    "mes": "Month",
    "factor": "Factor",
    "tasa final": "Factor",
    "tasa": "Factor",
    "sum insured": "Sum insured",
    "suma asegurada": "Sum insured",
    "suma_asegurada": "Sum insured",
    "renewal blocked": "Renewal blocked",
    "bloqueado": "Renewal blocked",
}

_FIXED_HEADERS = [
    "FixedRenewalData",
    "Year",
    "Month",
    "Chassis number",
    "Sum insured",
    "Factor",
    "Renewal blocked",
]


def _normalize_header(name: str) -> str:
    return _COL_ALIASES.get(name.strip().lower(), name.strip())


def _load_raw(path: Path) -> list[dict[str, Any]]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError(f"Empty workbook: {path}")

    raw_headers = [str(c) if c is not None else "" for c in rows[0]]
    headers = [_normalize_header(h) for h in raw_headers]

    required = {"Chassis number", "Year", "Month", "Factor"}
    missing = required - set(headers)
    if missing:
        raise ValueError(f"Missing required columns in input: {missing}")

    return [dict(zip(headers, row)) for row in rows[1:] if any(c is not None for c in row)]


def _write_lov(ws: Worksheet) -> None:
    lov_data: list[list[Any]] = json.loads(_LOV_FILE.read_text(encoding="utf-8"))
    for row in lov_data:
        ws.append(row)


def _write_fixed_renewal(ws: Worksheet, records: list[dict[str, Any]]) -> None:
    ws.append(_FIXED_HEADERS)
    for rec in records:
        row = [
            None,  # ID managed by framework
            rec.get("Year"),
            rec.get("Month"),
            rec.get("Chassis number"),
            rec.get("Sum insured"),
            rec.get("Factor"),
            rec.get("Renewal blocked", "No"),
        ]
        ws.append(row)


def generate(raw_input: Path, output: Path) -> None:
    """Transform *raw_input* Excel into a Flyway-ready ren_data Excel at *output*."""
    records = _load_raw(raw_input)

    wb = Workbook()
    # LOV must be first sheet
    ws_lov = wb.active
    ws_lov.title = "LOV"
    _write_lov(ws_lov)

    ws_data = wb.create_sheet("FixedRenewalData")
    _write_fixed_renewal(ws_data, records)

    wb.save(output)
