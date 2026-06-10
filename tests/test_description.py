"""Tests for src/description.py — auto-derivation of migration description and branch name."""

import pytest
from src.description import build_description, build_branch_name, _MONTH_ABBR


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


class TestBuildBranchName:
    def test_ren_data_uses_full_month_name(self) -> None:
        assert build_branch_name("ren-data", "ZNRX_67108", month=7) == "feature/ZNRX_67108_renov_julio"
        assert build_branch_name("ren-data", "ZNRX_67108", month=8) == "feature/ZNRX_67108_renov_agosto"
        assert build_branch_name("ren-data", "INC23438687", month=5) == "feature/INC23438687_renov_mayo"

    def test_ren_data_all_months_full_names(self) -> None:
        expected = {
            1: "enero", 2: "febrero",  3: "marzo",
            4: "abril", 5: "mayo",     6: "junio",
            7: "julio", 8: "agosto",   9: "septiembre",
            10: "octubre", 11: "noviembre", 12: "diciembre",
        }
        for month, name in expected.items():
            branch = build_branch_name("ren-data", "T_001", month=month)
            assert branch == f"feature/T_001_renov_{name}"

    def test_rules_entity_to_snake(self) -> None:
        assert build_branch_name("rules", "RITM_2500", entity="VHPlanRules") == "feature/RITM_2500_VH_Plan_Rules"
        assert build_branch_name("rules", "RITM_2500", entity="VHPlanSetup") == "feature/RITM_2500_VH_Plan_Setup"

    def test_ren_data_ticket_already_sanitized(self) -> None:
        # ticket should arrive pre-sanitized (hyphens already replaced in main.py)
        branch = build_branch_name("ren-data", "INC23703493", month=7)
        assert branch == "feature/INC23703493_renov_julio"
        assert "-" not in branch

    def test_ren_data_missing_month_raises(self) -> None:
        with pytest.raises(ValueError, match="month"):
            build_branch_name("ren-data", "T_001")

    def test_rules_missing_entity_raises(self) -> None:
        with pytest.raises(ValueError, match="entity"):
            build_branch_name("rules", "T_001")

    def test_unknown_command_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown command"):
            build_branch_name("infra", "T_001", month=8)
