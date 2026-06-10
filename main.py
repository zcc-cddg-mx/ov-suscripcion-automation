"""
CLI entry point for the OV subscription automation tool.

Usage examples:
  # Tipo 1 — vencimientos motor
  python main.py ren-data \\
      --input requirements/renovaciones/2026/agosto/baseticketAgosto2026.xlsx \\
      --ticket INC23999999 \\
      --description VH_ren_data_ago \\
      --year 2026 --month 8 \\
      --repo /path/to/ov-arizona-backend-ecuador \\
      [--commit]

  # Tipo 2 — reglas de tarificación
  python main.py rules \\
      --input data/raw_rules.xlsx \\
      --ticket RITM2500000 \\
      --entity VHPlanRules \\
      --repo /path/to/ov-arizona-backend-ecuador \\
      [--commit]
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from src import generator_ren_data, generator_rules, java_template, placer


def _timestamp() -> str:
    return datetime.now().strftime("%Y_%m_%d_%H_%M_%S")


def _build_base_name(ticket_id: str, description: str) -> str:
    ts = _timestamp()
    return f"V{ts}__{ticket_id}_{description}"


def cmd_ren_data(args: argparse.Namespace) -> None:
    raw_input = Path(args.input)
    repo_root = Path(args.repo)
    module = "ams-policy"
    description = args.description
    ticket_id = args.ticket

    base_name = _build_base_name(ticket_id, description)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        xlsx_out = tmp_path / f"{base_name}.xlsx"
        java_out = tmp_path / f"{base_name}.java"

        print(f"Generating Excel: {xlsx_out.name}")
        generator_ren_data.generate(raw_input, xlsx_out, year=args.year, month=args.month)

        print(f"Generating Java class: {java_out.name}")
        java_src = java_template.generate(base_name, module)
        java_out.write_text(java_src, encoding="utf-8")

        print(f"Placing files in repo ({module})...")
        xlsx_dest, java_dest = placer.place(xlsx_out, java_out, base_name, module, repo_root)
        print(f"  xlsx → {xlsx_dest.relative_to(repo_root)}")
        print(f"  java → {java_dest.relative_to(repo_root)}")

        if args.commit:
            print("Committing...")
            placer.git_add_commit(repo_root, [xlsx_dest, java_dest], ticket_id, description)
            print("Done.")
        else:
            print("Skipping commit (use --commit to auto-commit).")


def cmd_rules(args: argparse.Namespace) -> None:
    raw_input = Path(args.input)
    repo_root = Path(args.repo)
    module = "ams-rule"
    entity_name = args.entity
    ticket_id = args.ticket
    description = entity_name  # description == entity name for type 2

    resources_path = repo_root / placer._MODULE_RESOURCES_PATH[module]
    base_name = _build_base_name(ticket_id, description)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        xlsx_out = tmp_path / f"{base_name}.xlsx"
        java_out = tmp_path / f"{base_name}.java"

        print(f"Generating Excel: {xlsx_out.name}")
        generator_rules.generate(raw_input, xlsx_out, entity_name, resources_path)

        print(f"Generating Java class: {java_out.name}")
        java_src = java_template.generate(base_name, module)
        java_out.write_text(java_src, encoding="utf-8")

        print(f"Placing files in repo ({module})...")
        xlsx_dest, java_dest = placer.place(xlsx_out, java_out, base_name, module, repo_root)
        print(f"  xlsx → {xlsx_dest.relative_to(repo_root)}")
        print(f"  java → {java_dest.relative_to(repo_root)}")

        if args.commit:
            print("Committing...")
            placer.git_add_commit(repo_root, [xlsx_dest, java_dest], ticket_id, description)
            print("Done.")
        else:
            print("Skipping commit (use --commit to auto-commit).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OV subscription migration automation"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ---- ren-data ----
    p_ren = sub.add_parser("ren-data", help="Tipo 1: vencimientos motor (ams-policy)")
    p_ren.add_argument("--input", required=True, help="Raw business Excel file (baseticketMES.xlsx from negocio)")
    p_ren.add_argument("--ticket", required=True, help="Ticket ID (e.g. INC23999999)")
    p_ren.add_argument("--description", required=True, help="Migration description (e.g. VH_ren_data_ago)")
    p_ren.add_argument("--year", required=True, type=int, help="Renewal year (e.g. 2026)")
    p_ren.add_argument("--month", required=True, type=int, help="Renewal month number (e.g. 8 for agosto)")
    p_ren.add_argument("--repo", required=True, help="Path to ov-arizona-backend-ecuador repo root")
    p_ren.add_argument("--commit", action="store_true", help="Auto-commit to git")

    # ---- rules ----
    p_rules = sub.add_parser("rules", help="Tipo 2: reglas de tarificación (ams-rule)")
    p_rules.add_argument("--input", required=True, help="Raw business Excel file")
    p_rules.add_argument("--ticket", required=True, help="Ticket ID (e.g. RITM2500000)")
    p_rules.add_argument("--entity", required=True, help="Entity name (e.g. VHPlanRules)")
    p_rules.add_argument("--repo", required=True, help="Path to ov-arizona-backend-ecuador repo root")
    p_rules.add_argument("--commit", action="store_true", help="Auto-commit to git")

    args = parser.parse_args()
    if args.command == "ren-data":
        cmd_ren_data(args)
    elif args.command == "rules":
        cmd_rules(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
