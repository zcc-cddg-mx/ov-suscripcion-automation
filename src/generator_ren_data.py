"""
Generator for migration type 1: VH_ren_data (ams-policy).

Transforms a raw business Excel into the Flyway-ready Excel with sheets: LOV, FixedRenewalData.

Expected input (real files from negocio):
  - Columns: CHASIS, TASA FINAL, PLACAS  (+ possible empty trailing columns)
  - Year and Month are NOT in the file — must be passed as arguments.
  - Rows with TASA FINAL == 'No Renovar' are excluded from the migration.
  - The file contains empty trailing rows that are filtered automatically.
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

_NO_RENOVAR = "no renovar"


def _normalize_header(name: str) -> str:
    return _COL_ALIASES.get(name.strip().lower(), name.strip())


def _load_raw(path: Path, year: int, month: int) -> list[dict[str, Any]]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError(f"Empty workbook: {path}")

    raw_headers = [str(c) if c is not None else "" for c in rows[0]]
    headers = [_normalize_header(h) for h in raw_headers]

    has_year = "Year" in headers
    has_month = "Month" in headers

    required = {"Chassis number", "Factor"}
    missing = required - set(headers)
    if missing:
        raise ValueError(f"Missing required columns in input: {missing}")

    records = []
    skipped_no_renovar = 0
    for raw_row in rows[1:]:
        if not any(c is not None for c in raw_row):
            continue  # skip empty trailing rows

        rec = dict(zip(headers, raw_row))

        factor = rec.get("Factor")
        if isinstance(factor, str) and factor.strip().lower() == _NO_RENOVAR:
            skipped_no_renovar += 1
            continue

        # Inject year/month from arguments if not present in the file
        if not has_year:
            rec["Year"] = year
        if not has_month:
            rec["Month"] = month

        records.append(rec)

    if skipped_no_renovar:
        print(f"  Skipped {skipped_no_renovar} rows with 'No Renovar'")

    return records


def _write_lov(ws: Worksheet) -> None:
    lov_data: list[list[Any]] = json.loads(_LOV_FILE.read_text(encoding="utf-8"))
    for row in lov_data:
        ws.append(row)


def _write_fixed_renewal(ws: Worksheet, records: list[dict[str, Any]]) -> None:
    ws.append(_FIXED_HEADERS)
    for rec in records:
        ws.append([
            None,
            rec.get("Year"),
            rec.get("Month"),
            rec.get("Chassis number"),
            rec.get("Sum insured"),
            rec.get("Factor"),
            rec.get("Renewal blocked", "No"),
        ])


def generate(raw_input: Path, output: Path, year: int, month: int) -> None:
    """
    Transform *raw_input* Excel into a Flyway-ready ren_data Excel at *output*.

    *year* and *month* are required because real business files from negocio
    do not include those columns — only CHASIS and TASA FINAL.
    """
    records = _load_raw(raw_input, year, month)
    if not records:
        raise ValueError("No valid records found after filtering. Check the input file.")

    wb = Workbook()
    ws_lov = wb.active
    ws_lov.title = "LOV"
    _write_lov(ws_lov)

    ws_data = wb.create_sheet("FixedRenewalData")
    _write_fixed_renewal(ws_data, records)

    wb.save(output)
    print(f"  {len(records)} records written to {output.name}")
