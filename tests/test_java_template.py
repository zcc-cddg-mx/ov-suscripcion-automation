"""Tests for java_template."""

import pytest
from src.java_template import generate


class TestJavaTemplate:
    def test_ams_rule_package(self) -> None:
        code = generate("V2026_06_10_12_00_00__RITM001_VHPlanRules", "ams-rule")
        assert "package eu.ncdc.arizona.rule.db.migration;" in code
        assert "import eu.ncdc.arizona.migration.task.LoadFromFileMigrationTask;" in code
        assert "public class V2026_06_10_12_00_00__RITM001_VHPlanRules extends LoadFromFileMigrationTask {" in code

    def test_ams_policy_package(self) -> None:
        code = generate("V2026_06_10_12_00_00__INC999_VH_ren_data_aug", "ams-policy")
        assert "package eu.ncdc.arizona.policy.db.migration;" in code

    def test_unknown_module_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown module"):
            generate("V2026_06_10_12_00_00__INC999_Test", "ams-unknown")
