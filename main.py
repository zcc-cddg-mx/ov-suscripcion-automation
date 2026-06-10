"""
CLI entry point for the OV subscription automation tool.

Usage examples:
  # Tipo 1 — vencimientos motor (description auto-derived if omitted)
  python main.py ren-data \\
      --input requirements/renovaciones/2026/agosto/baseticketAgosto2026.xlsx \\
      --ticket INC23999999 \\
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

  # Modo payload (para integración con n8n — repo leído de config.json)
  python main.py run-payload --payload /path/to/payload.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from src import generator_ren_data, generator_rules, java_template, placer
from src.config import load_config
from src.description import build_description, build_branch_name


def _timestamp() -> str:
    return datetime.now().strftime("%Y_%m_%d_%H_%M_%S")


def _sanitize_ticket(ticket_id: str) -> str:
    """Replace hyphens with underscores — Flyway rejects hyphens in class/file names."""
    return ticket_id.replace("-", "_")


def _build_base_name(ticket_id: str, description: str) -> str:
    ts = _timestamp()
    return f"V{ts}__{_sanitize_ticket(ticket_id)}_{description}"


def cmd_ren_data(args: argparse.Namespace) -> None:
    raw_input = Path(args.input)
    repo_root = Path(args.repo)
    module = "ams-policy"
    ticket_id = args.ticket
    ticket_safe = _sanitize_ticket(ticket_id)

    description = args.description or build_description(
        "ren-data", month=args.month, year=args.year
    )
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

        if args.commit:
            branch = build_branch_name("ren-data", ticket_safe, month=args.month)
            print(f"Creating feature branch: {branch}")
            placer.create_feature_branch(repo_root, branch)

        print(f"Placing files in repo ({module})...")
        xlsx_dest, java_dest = placer.place(xlsx_out, java_out, base_name, module, repo_root)
        print(f"  xlsx → {xlsx_dest.relative_to(repo_root)}")
        print(f"  java → {java_dest.relative_to(repo_root)}")

        if args.commit:
            print("Committing...")
            placer.git_add_commit(repo_root, [xlsx_dest, java_dest], ticket_id, description)
            print("Done.")
        else:
            print("Skipping branch + commit (use --commit to auto-commit).")


def cmd_rules(args: argparse.Namespace) -> None:
    raw_input = Path(args.input)
    repo_root = Path(args.repo)
    module = "ams-rule"
    entity_name = args.entity
    ticket_id = args.ticket
    ticket_safe = _sanitize_ticket(ticket_id)
    description = entity_name

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

        if args.commit:
            branch = build_branch_name("rules", ticket_safe, entity=entity_name)
            print(f"Creating feature branch: {branch}")
            placer.create_feature_branch(repo_root, branch)

        print(f"Placing files in repo ({module})...")
        xlsx_dest, java_dest = placer.place(xlsx_out, java_out, base_name, module, repo_root)
        print(f"  xlsx → {xlsx_dest.relative_to(repo_root)}")
        print(f"  java → {java_dest.relative_to(repo_root)}")

        if args.commit:
            print("Committing...")
            placer.git_add_commit(repo_root, [xlsx_dest, java_dest], ticket_id, description)
            print("Done.")
        else:
            print("Skipping branch + commit (use --commit to auto-commit).")


def cmd_run_payload(args: argparse.Namespace) -> None:
    """Execute a migration from a structured JSON payload (n8n integration)."""
    payload_path = Path(args.payload)
    if not payload_path.exists():
        print(f"Payload file not found: {payload_path}", file=sys.stderr)
        sys.exit(1)

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    cfg = load_config()
    repo_root = Path(cfg["repo"])

    command = payload.get("command")
    if not command:
        print("Payload missing required field: 'command'", file=sys.stderr)
        sys.exit(1)

    description = build_description(
        command,
        month=payload.get("month"),
        year=payload.get("year"),
        entity=payload.get("entity"),
    )

    ns = argparse.Namespace(
        input=payload["input"],
        ticket=payload["ticket"],
        description=description,
        repo=str(repo_root),
        commit=payload.get("commit", False),
        year=payload.get("year"),
        month=payload.get("month"),
        entity=payload.get("entity"),
    )

    print(f"Running payload: command={command}, ticket={payload['ticket']}, description={description}")

    if command == "ren-data":
        cmd_ren_data(ns)
    elif command == "rules":
        cmd_rules(ns)
    else:
        print(f"Unknown command in payload: {command!r}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OV subscription migration automation"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ---- ren-data ----
    p_ren = sub.add_parser("ren-data", help="Tipo 1: vencimientos motor (ams-policy)")
    p_ren.add_argument("--input", required=True, help="Raw business Excel file (baseticketMES.xlsx from negocio)")
    p_ren.add_argument("--ticket", required=True, help="Ticket ID (e.g. ZNRX-67108 or INC23999999)")
    p_ren.add_argument("--description", default=None,
                       help="Migration description suffix (optional — auto-derived from year+month if omitted)")
    p_ren.add_argument("--year", required=True, type=int, help="Renewal year (e.g. 2026)")
    p_ren.add_argument("--month", required=True, type=int, help="Renewal month number (e.g. 8 for agosto)")
    p_ren.add_argument("--repo", required=True, help="Path to ov-arizona-backend-ecuador repo root")
    p_ren.add_argument("--commit", action="store_true",
                       help="Create feature branch from develop, place files, and commit")

    # ---- rules ----
    p_rules = sub.add_parser("rules", help="Tipo 2: reglas de tarificación (ams-rule)")
    p_rules.add_argument("--input", required=True, help="Raw business Excel file")
    p_rules.add_argument("--ticket", required=True, help="Ticket ID (e.g. ZNRX-67108 or RITM2500000)")
    p_rules.add_argument("--entity", required=True, help="Entity name (e.g. VHPlanRules)")
    p_rules.add_argument("--repo", required=True, help="Path to ov-arizona-backend-ecuador repo root")
    p_rules.add_argument("--commit", action="store_true",
                         help="Create feature branch from develop, place files, and commit")

    # ---- run-payload ----
    p_payload = sub.add_parser("run-payload", help="Run from JSON payload (n8n integration)")
    p_payload.add_argument("--payload", required=True, help="Path to JSON payload file")

    args = parser.parse_args()
    if args.command == "ren-data":
        cmd_ren_data(args)
    elif args.command == "rules":
        cmd_rules(args)
    elif args.command == "run-payload":
        cmd_run_payload(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
