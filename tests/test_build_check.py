"""Tests for src/build_check.py."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.build_check import verify, BuildCheckError


def _make_success():
    m = MagicMock()
    m.returncode = 0
    m.stdout = ""
    m.stderr = ""
    return m


def _make_failure(output: str):
    m = MagicMock()
    m.returncode = 1
    m.stdout = output
    m.stderr = ""
    return m


class TestVerify:
    def test_unknown_module_raises_build_check_error(self, tmp_path: Path) -> None:
        with pytest.raises(BuildCheckError, match="Unknown module"):
            verify(tmp_path, "ams-unknown")

    def test_gradle_success_returns_none(self, tmp_path: Path) -> None:
        with patch("src.build_check._LOCAL_SETUP_SCRIPT", Path("/nonexistent")), \
             patch("subprocess.run", return_value=_make_success()):
            result = verify(tmp_path, "ams-policy")
        assert result is None

    def test_gradle_failure_raises_build_check_error(self, tmp_path: Path) -> None:
        with patch("src.build_check._LOCAL_SETUP_SCRIPT", Path("/nonexistent")), \
             patch("subprocess.run", return_value=_make_failure("error: ';' expected")):
            with pytest.raises(BuildCheckError, match="Compilation failed"):
                verify(tmp_path, "ams-policy")

    def test_error_message_contains_module_name(self, tmp_path: Path) -> None:
        with patch("src.build_check._LOCAL_SETUP_SCRIPT", Path("/nonexistent")), \
             patch("subprocess.run", return_value=_make_failure("some error")):
            with pytest.raises(BuildCheckError) as exc_info:
                verify(tmp_path, "ams-rule")
        assert "ams-rule" in str(exc_info.value)

    def test_setup_script_failure_raises_build_check_error(self, tmp_path: Path) -> None:
        setup_fail = MagicMock()
        setup_fail.returncode = 1
        setup_fail.stderr = "setup failed"

        with patch("src.build_check._LOCAL_SETUP_SCRIPT", tmp_path / "setup.sh") as mock_path, \
             patch("subprocess.run", return_value=setup_fail):
            # Create dummy script file so exists() returns True
            (tmp_path / "setup.sh").write_text("exit 1")
            with pytest.raises(BuildCheckError, match="setup-local-gradle"):
                verify(tmp_path, "ams-policy")

    def test_ams_rule_uses_correct_gradle_path(self, tmp_path: Path) -> None:
        calls = []

        def capture_run(cmd, **kwargs):
            calls.append(cmd)
            return _make_success()

        with patch("src.build_check._LOCAL_SETUP_SCRIPT", Path("/nonexistent")), \
             patch("subprocess.run", side_effect=capture_run):
            verify(tmp_path, "ams-rule")

        gradle_call = next(c for c in calls if "gradle" in str(c))
        assert ":ams-rule:flyway:compileJava" in gradle_call

    def test_ams_policy_uses_correct_gradle_path(self, tmp_path: Path) -> None:
        calls = []

        def capture_run(cmd, **kwargs):
            calls.append(cmd)
            return _make_success()

        with patch("src.build_check._LOCAL_SETUP_SCRIPT", Path("/nonexistent")), \
             patch("subprocess.run", side_effect=capture_run):
            verify(tmp_path, "ams-policy")

        gradle_call = next(c for c in calls if "gradle" in str(c))
        assert ":ams-policy:flyway:compileJava" in gradle_call
