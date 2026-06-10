"""Auto-derives the migration description from command + context.

The description becomes the suffix in the Flyway filename:
  V{ts}__{TICKET}_{description}

Rules:
  ren-data → VH_ren_data_{month_abbr}_{year}   e.g. VH_ren_data_ago_2026
  rules    → {entity_name}                      e.g. VHPlanRules
"""

from __future__ import annotations

_MONTH_ABBR: dict[int, str] = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr",
    5: "may", 6: "jun", 7: "jul", 8: "ago",
    9: "sep", 10: "oct", 11: "nov", 12: "dic",
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
