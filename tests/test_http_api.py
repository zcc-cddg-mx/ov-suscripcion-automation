"""Tests for the HTTP API listener (app.py).

Uses Flask test client — no real server, no git operations.
All migration logic is mocked so these tests are fast and self-contained.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import app as app_module
from app import app
from src.build_check import BuildCheckError


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── /health ───────────────────────────────────────────────────────────────────

class TestHealth:
    def test_returns_200(self, client) -> None:
        r = client.get("/health")
        assert r.status_code == 200

    def test_returns_ok_json(self, client) -> None:
        data = r = client.get("/health").get_json()
        assert data["status"] == "ok"
        assert data["service"] == "code-agent"


# ── /run — request validation ─────────────────────────────────────────────────

class TestRunRequestValidation:
    def test_non_json_body_returns_400(self, client) -> None:
        r = client.post("/run", data="not json", content_type="text/plain")
        assert r.status_code == 400
        assert r.get_json()["status"] == "error"

    def test_empty_body_returns_400(self, client) -> None:
        r = client.post("/run")
        assert r.status_code == 400

    def test_missing_command_returns_422(self, client) -> None:
        r = client.post("/run", json={"ticket": "INC001", "input": "x.xlsx"})
        assert r.status_code == 422
        body = r.get_json()
        assert body["status"] == "error"
        assert "command" in body["error"].lower()

    def test_unknown_command_returns_422(self, client) -> None:
        r = client.post("/run", json={
            "command": "infra-change", "ticket": "INC001", "input": "x.xlsx"
        })
        assert r.status_code == 422
        assert r.get_json()["status"] == "error"


# ── /run — success path ───────────────────────────────────────────────────────

_REN_DATA_PAYLOAD = {
    "command": "ren-data",
    "ticket": "ZNRX-67108",
    "input": "requirements/renovaciones/2026/agosto/baseticketAgosto2026.xlsx",
    "year": 2026,
    "month": 8,
    "commit": False,
}

_RULES_PAYLOAD = {
    "command": "rules",
    "ticket": "RITM2500000",
    "input": "data/raw.xlsx",
    "entity": "VHPlanRules",
    "commit": False,
}

_MOCK_RESULT = {
    "branch": None,
    "commit_id": None,
    "aux_branch": None,
    "base_name": "V2026_01_01_00_00_00__ZNRX_67108_VH_ren_data_ago_2026",
    "module": "ams-policy",
}

_MOCK_CONFIG = {"repo": "../ov-arizona-backend-ecuador"}


class TestRunSuccess:
    def test_ren_data_returns_success_status(self, client) -> None:
        with patch("app.run_payload", return_value=_MOCK_RESULT), \
             patch("app.load_config", return_value=_MOCK_CONFIG):
            r = client.post("/run", json=_REN_DATA_PAYLOAD)
        assert r.status_code == 200
        assert r.get_json()["status"] == "success"

    def test_response_contains_required_fields(self, client) -> None:
        with patch("app.run_payload", return_value=_MOCK_RESULT), \
             patch("app.load_config", return_value=_MOCK_CONFIG):
            body = client.post("/run", json=_REN_DATA_PAYLOAD).get_json()
        for field in ("status", "branch", "commit_id", "repo", "build_status", "summary"):
            assert field in body, f"Missing field: {field}"

    def test_repo_name_extracted_from_config(self, client) -> None:
        with patch("app.run_payload", return_value=_MOCK_RESULT), \
             patch("app.load_config", return_value=_MOCK_CONFIG):
            body = client.post("/run", json=_REN_DATA_PAYLOAD).get_json()
        assert body["repo"] == "ov-arizona-backend-ecuador"

    def test_rules_payload_also_returns_success(self, client) -> None:
        mock_result = {**_MOCK_RESULT, "base_name": "V2026_01_01__RITM_2500000_VHPlanRules",
                       "module": "ams-rule"}
        with patch("app.run_payload", return_value=mock_result), \
             patch("app.load_config", return_value=_MOCK_CONFIG):
            r = client.post("/run", json=_RULES_PAYLOAD)
        assert r.status_code == 200
        assert r.get_json()["status"] == "success"

    def test_no_commit_summary_says_generated(self, client) -> None:
        with patch("app.run_payload", return_value=_MOCK_RESULT), \
             patch("app.load_config", return_value=_MOCK_CONFIG):
            body = client.post("/run", json=_REN_DATA_PAYLOAD).get_json()
        assert "generated" in body["summary"].lower()
        assert body["branch"] is None
        assert body["commit_id"] is None

    def test_with_commit_summary_contains_branch(self, client) -> None:
        result_with_commit = {
            **_MOCK_RESULT,
            "branch": "feature/ZNRX_67108_renov_agosto",
            "commit_id": "abc123def456",
        }
        with patch("app.run_payload", return_value=result_with_commit), \
             patch("app.load_config", return_value=_MOCK_CONFIG):
            body = client.post("/run", json={**_REN_DATA_PAYLOAD, "commit": True}).get_json()
        assert "feature/ZNRX_67108_renov_agosto" in body["summary"]
        assert body["commit_id"] == "abc123def456"


# ── /run — error paths ────────────────────────────────────────────────────────

class TestRunErrors:
    def test_value_error_returns_422(self, client) -> None:
        with patch("app.run_payload", side_effect=ValueError("Validation failed: bad input")):
            r = client.post("/run", json=_REN_DATA_PAYLOAD)
        assert r.status_code == 422
        body = r.get_json()
        assert body["status"] == "error"
        assert "Validation failed" in body["error"]
        assert body["build_status"] is None

    def test_unexpected_exception_returns_500(self, client) -> None:
        with patch("app.run_payload", side_effect=RuntimeError("git push failed")):
            r = client.post("/run", json=_REN_DATA_PAYLOAD)
        assert r.status_code == 500
        body = r.get_json()
        assert body["status"] == "error"
        assert body["build_status"] is None

    def test_build_check_error_returns_422_with_failed_status(self, client) -> None:
        with patch("app.run_payload", side_effect=BuildCheckError("Compilation failed:\nerror: ';' expected")):
            r = client.post("/run", json=_REN_DATA_PAYLOAD)
        assert r.status_code == 422
        body = r.get_json()
        assert body["status"] == "error"
        assert body["build_status"] == "failed"
        assert "Compilation failed" in body["error"]
