"""Tests for generator_ren_data."""

import tempfile
from pathlib import Path

import openpyxl
import pytest

from src.generator_ren_data import generate


def _make_raw_input(path: Path, rows: list[dict]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = ["chassis", "year", "month", "factor", "sum insured", "renewal blocked"]
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h) for h in headers])
    wb.save(path)


class TestGeneratorRenData:
    def test_basic_output_structure(self, tmp_path: Path) -> None:
        raw = tmp_path / "raw.xlsx"
        _make_raw_input(raw, [
            {"chassis": "ABC123", "year": 2026, "month": 8, "factor": 0.02, "sum insured": None, "renewal blocked": "No"},
            {"chassis": "XYZ999", "year": 2026, "month": 8, "factor": 0.015, "sum insured": 10000, "renewal blocked": "No"},
        ])

        out = tmp_path / "output.xlsx"
        generate(raw, out)

        assert out.exists()
        wb = openpyxl.load_workbook(out, data_only=True)
        assert wb.sheetnames == ["LOV", "FixedRenewalData"]

    def test_lov_sheet_has_289_rows(self, tmp_path: Path) -> None:
        raw = tmp_path / "raw.xlsx"
        _make_raw_input(raw, [
            {"chassis": "TEST001", "year": 2026, "month": 9, "factor": 0.019, "sum insured": None, "renewal blocked": "No"},
        ])
        out = tmp_path / "output.xlsx"
        generate(raw, out)

        wb = openpyxl.load_workbook(out, data_only=True)
        ws_lov = wb["LOV"]
        rows = [r for r in ws_lov.iter_rows(values_only=True) if any(c is not None for c in r)]
        assert len(rows) == 289

    def test_fixed_renewal_data_headers(self, tmp_path: Path) -> None:
        raw = tmp_path / "raw.xlsx"
        _make_raw_input(raw, [
            {"chassis": "TEST001", "year": 2026, "month": 9, "factor": 0.019, "sum insured": None, "renewal blocked": "No"},
        ])
        out = tmp_path / "output.xlsx"
        generate(raw, out)

        wb = openpyxl.load_workbook(out, data_only=True)
        ws = wb["FixedRenewalData"]
        headers = [ws.cell(1, col).value for col in range(1, 8)]
        assert headers == [
            "FixedRenewalData", "Year", "Month",
            "Chassis number", "Sum insured", "Factor", "Renewal blocked",
        ]

    def test_data_rows_count(self, tmp_path: Path) -> None:
        raw = tmp_path / "raw.xlsx"
        records = [
            {"chassis": f"CHASSIS{i:03}", "year": 2026, "month": 8, "factor": 0.02, "sum insured": None, "renewal blocked": "No"}
            for i in range(5)
        ]
        _make_raw_input(raw, records)
        out = tmp_path / "output.xlsx"
        generate(raw, out)

        wb = openpyxl.load_workbook(out, data_only=True)
        ws = wb["FixedRenewalData"]
        # 1 header + 5 data rows
        assert ws.max_row == 6

    def test_id_column_is_none(self, tmp_path: Path) -> None:
        raw = tmp_path / "raw.xlsx"
        _make_raw_input(raw, [
            {"chassis": "CHASSIS001", "year": 2026, "month": 8, "factor": 0.02, "sum insured": None, "renewal blocked": "No"},
        ])
        out = tmp_path / "output.xlsx"
        generate(raw, out)

        wb = openpyxl.load_workbook(out, data_only=True)
        ws = wb["FixedRenewalData"]
        assert ws.cell(2, 1).value is None

    def test_missing_required_column_raises(self, tmp_path: Path) -> None:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["year", "month", "factor"])  # missing chassis
        ws.append([2026, 8, 0.02])
        raw = tmp_path / "bad.xlsx"
        wb.save(raw)
        out = tmp_path / "output.xlsx"
        with pytest.raises(ValueError, match="Missing required columns"):
            generate(raw, out)

    def test_accepts_spanish_column_names(self, tmp_path: Path) -> None:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["chasis", "año", "mes", "factor", "suma asegurada", "bloqueado"])
        ws.append(["ABC123", 2026, 8, 0.02, None, "No"])
        raw = tmp_path / "spanish.xlsx"
        wb.save(raw)
        out = tmp_path / "output.xlsx"
        generate(raw, out)  # should not raise

        wb2 = openpyxl.load_workbook(out, data_only=True)
        ws_out = wb2["FixedRenewalData"]
        assert ws_out.cell(2, 4).value == "ABC123"  # Chassis number in col 4
