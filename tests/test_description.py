"""Tests for src/description.py — auto-derivation of migration description."""

import pytest
from src.description import build_description, _MONTH_ABBR


class TestBuildDescription:
    def test_ren_data_all_months(self) -> None:
        expected = {
            1: "VH_ren_data_ene_2026",
            2: "VH_ren_data_feb_2026",
            3: "VH_ren_data_mar_2026",
            4: "VH_ren_data_abr_2026",
            5: "VH_ren_data_may_2026",
            6: "VH_ren_data_jun_2026",
            7: "VH_ren_data_jul_2026",
            8: "VH_ren_data_ago_2026",
            9: "VH_ren_data_sep_2026",
            10: "VH_ren_data_oct_2026",
            11: "VH_ren_data_nov_2026",
            12: "VH_ren_data_dic_2026",
        }
        for month, desc in expected.items():
            assert build_description("ren-data", month=month, year=2026) == desc

    def test_ren_data_different_year(self) -> None:
        assert build_description("ren-data", month=3, year=2027) == "VH_ren_data_mar_2027"

    def test_rules_returns_entity(self) -> None:
        assert build_description("rules", entity="VHPlanRules") == "VHPlanRules"

    def test_rules_preserves_entity_case(self) -> None:
        assert build_description("rules", entity="VHPlanSetup") == "VHPlanSetup"

    def test_ren_data_missing_month_raises(self) -> None:
        with pytest.raises(ValueError, match="month"):
            build_description("ren-data", year=2026)

    def test_ren_data_missing_year_raises(self) -> None:
        with pytest.raises(ValueError, match="year"):
            build_description("ren-data", month=8)

    def test_ren_data_invalid_month_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid month"):
            build_description("ren-data", month=13, year=2026)

    def test_rules_missing_entity_raises(self) -> None:
        with pytest.raises(ValueError, match="entity"):
            build_description("rules")

    def test_unknown_command_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown command"):
            build_description("unknown-type", month=8, year=2026)
