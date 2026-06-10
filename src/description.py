"""Auto-derives the migration description and feature branch name from command + context.

Flyway filename suffix:
  ren-data → VH_ren_data_{month_abbr}_{year}   e.g. VH_ren_data_ago_2026
  rules    → {entity_name}                      e.g. VHPlanRules

Feature branch name (base branch: develop):
  ren-data → feature/{ticket_sanitized}_renov_{month_full}   e.g. feature/ZNRX_67108_renov_julio
  rules    → feature/{ticket_sanitized}_{entity_snake}       e.g. feature/RITM_2500_VH_Plan_Rules
"""

from __future__ import annotations

import re

_MONTH_ABBR: dict[int, str] = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr",
    5: "may", 6: "jun", 7: "jul", 8: "ago",
    9: "sep", 10: "oct", 11: "nov", 12: "dic",
}

_MONTH_FULL: dict[int, str] = {
    1: "enero",      2: "febrero",   3: "marzo",
    4: "abril",      5: "mayo",      6: "junio",
    7: "julio",      8: "agosto",    9: "septiembre",
    10: "octubre",   11: "noviembre", 12: "diciembre",
}


def build_description(
    command: str,
    *,
    month: int | None = None,
    year: int | None = None,
    entity: str | None = None,
) -> str:
    if command == "ren-data":
        if month is None or year is None:
            raise ValueError("ren-data description requires 'month' and 'year'")
        abbr = _MONTH_ABBR.get(month)
        if abbr is None:
            raise ValueError(f"Invalid month: {month}. Must be 1–12.")
        return f"VH_ren_data_{abbr}_{year}"
    if command == "rules":
        if not entity:
            raise ValueError("rules description requires 'entity'")
        return entity
    raise ValueError(f"Unknown command: {command!r}")


def _entity_to_snake(entity: str) -> str:
    """VHPlanRules → VH_Plan_Rules (for use in branch names)."""
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", entity)
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", s)
    return s


def build_branch_name(
    command: str,
    ticket_sanitized: str,
    *,
    month: int | None = None,
    entity: str | None = None,
) -> str:
    """Return the feature branch name for the given migration.

    ren-data → feature/{ticket}_renov_{month_full}   e.g. feature/ZNRX_67108_renov_julio
    rules    → feature/{ticket}_{entity_snake}        e.g. feature/RITM_2500_VH_Plan_Rules
    """
    if command == "ren-data":
        if month is None:
            raise ValueError("ren-data branch name requires 'month'")
        month_name = _MONTH_FULL.get(month)
        if month_name is None:
            raise ValueError(f"Invalid month: {month}. Must be 1–12.")
        return f"feature/{ticket_sanitized}_renov_{month_name}"
    if command == "rules":
        if not entity:
            raise ValueError("rules branch name requires 'entity'")
        return f"feature/{ticket_sanitized}_{_entity_to_snake(entity)}"
    raise ValueError(f"Unknown command: {command!r}")
