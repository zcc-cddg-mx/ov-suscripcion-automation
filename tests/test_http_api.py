"""Tests for the HTTP API listener (app.py).

Uses Flask test client — no real server, no git operations.
Migration logic is mocked so these tests are fast and self-contained.

Architecture:
  POST /run → 202 Accepted immediately (queued | rejected)
  GET  /status/<task_id> → task state from SQLite
  GET  /tasks → recent task list

All /run requests must use multipart/form-data with a real file attachment.
"""

from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault("TASKS_DB", "/tmp/test_tasks_api.db")
sys.path.insert(0, str(Path(__file__).parent.parent))

import app as app_module
from app import app
from src.build_check import BuildCheckError


@pytest.fixture
def client(tmp_path):
    app.config["TESTING"] = True
    with patch("app._UPLOADS_DIR", tmp_path / "uploads"):
        with app.test_client() as c:
            yield c


def _multipart(command: str, ticket: str = "INC001", extra: dict | None = None) -> dict:
    """Build a multipart/form-data dict with a dummy xlsx file."""
    data: dict = {
        "file": (io.BytesIO(b"PK\x03\x04dummy"), "input.xlsx", "application/octet-stream"),
        "command": command,
        "ticket": ticket,
    }
    if extra:
        data.update(extra)
    return data


# ── /health ───────────────────────────────────────────────────────────────────

class TestHealth:
    def test_returns_200(self, client) -> None:
        r = client.get("/health")
        assert r.status_code == 200

    def test_returns_ok_json(self, client) -> None:
        data = client.get("/health").get_json()
        assert data["status"] == "ok"
        assert data["service"] == "code-agent"


# ── /run — request validation ─────────────────────────────────────────────────

class TestRunRequestValidation:
    def test_wrong_content_type_returns_400(self, client) -> None:
        r = client.post("/run", data="not multipart", content_type="text/plain")
        assert r.status_code == 400
        assert r.get_json()["status"] == "error"

    def test_empty_body_returns_400(self, client) -> None:
        r = client.post("/run")
        assert r.status_code == 400

    def test_missing_file_returns_400(self, client) -> None:
        r = client.post("/run", data={"command": "ren-data", "ticket": "INC001",
                                      "year": "2026", "month": "8"},
                        content_type="multipart/form-data")
        assert r.status_code == 400
        assert "file" in r.get_json()["error"].lower()

    def test_ren_data_missing_year_returns_400(self, client) -> None:
        data = _multipart("ren-data", extra={"month": "8"})
        r = client.post("/run", data=data, content_type="multipart/form-data")
        assert r.status_code == 400
        assert "year" in r.get_json()["error"].lower()

    def test_ren_data_missing_month_returns_400(self, client) -> None:
        data = _multipart("ren-data", extra={"year": "2026"})
        r = client.post("/run", data=data, content_type="multipart/form-data")
        assert r.status_code == 400
        assert "month" in r.get_json()["error"].lower()

    def test_rules_missing_entity_returns_400(self, client) -> None:
        data = _multipart("rules")
        r = client.post("/run", data=data, content_type="multipart/form-data")
        assert r.status_code == 400
        assert "entity" in r.get_json()["error"].lower()

    def test_rules_with_entity_accepted(self, client) -> None:
        data = _multipart("rules", extra={"entity": "VHDriversAge"})
        with patch("app.run_payload", return_value={"branch": None, "commit_id": None,
                   "aux_branch": None, "base_name": "V_test", "module": "ams-rule"}), \
             patch("app.load_config", return_value={"repo": "../ov-arizona-backend-ecuador"}):
            r = client.post("/run", data=data, content_type="multipart/form-data")
        assert r.status_code == 202
        assert r.get_json()["status"] in ("queued", "rejected")


# ── /run — accepted (202) ─────────────────────────────────────────────────────

class TestRunAccepted:
    def test_ren_data_returns_202(self, client) -> None:
        data = _multipart("ren-data", extra={"year": "2026", "month": "8"})
        with patch("app.run_payload", return_value={"branch": None, "commit_id": None,
                   "aux_branch": None, "base_name": "V_test", "module": "ams-policy"}), \
             patch("app.load_config", return_value={"repo": "../ov-arizona-backend-ecuador"}):
            r = client.post("/run", data=data, content_type="multipart/form-data")
        assert r.status_code == 202
        body = r.get_json()
        assert body["status"] in ("queued", "rejected")
        assert "task_id" in body

    def test_rules_returns_202(self, client) -> None:
        data = _multipart("rules", extra={"entity": "VHDriversAge"})
        with patch("app.run_payload", return_value={"branch": None, "commit_id": None,
                   "aux_branch": None, "base_name": "V_test", "module": "ams-rule"}), \
             patch("app.load_config", return_value={"repo": "../ov-arizona-backend-ecuador"}):
            r = client.post("/run", data=data, content_type="multipart/form-data")
        assert r.status_code == 202

    def test_task_id_in_response(self, client) -> None:
        data = _multipart("ren-data", extra={"year": "2026", "month": "8"})
        with patch("app.run_payload", return_value={"branch": None, "commit_id": None,
                   "aux_branch": None, "base_name": "V_test", "module": "ams-policy"}), \
             patch("app.load_config", return_value={"repo": "../ov-arizona-backend-ecuador"}):
            body = client.post("/run", data=data, content_type="multipart/form-data").get_json()
        assert len(body["task_id"]) == 8


# ── /status and /tasks ────────────────────────────────────────────────────────

class TestStatusAndTasks:
    def test_unknown_task_returns_404(self, client) -> None:
        r = client.get("/status/nonexistent")
        assert r.status_code == 404

    def test_tasks_returns_list(self, client) -> None:
        r = client.get("/tasks")
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

    def test_tasks_limit_param(self, client) -> None:
        r = client.get("/tasks?limit=5")
        assert r.status_code == 200

    def test_queued_task_visible_in_status(self, client) -> None:
        data = _multipart("ren-data", extra={"year": "2026", "month": "8"})
        with patch("app.run_payload", return_value={"branch": None, "commit_id": None,
                   "aux_branch": None, "base_name": "V_test", "module": "ams-policy"}), \
             patch("app.load_config", return_value={"repo": "../ov-arizona-backend-ecuador"}):
            body = client.post("/run", data=data, content_type="multipart/form-data").get_json()

        task_id = body.get("task_id")
        if task_id:
            r = client.get(f"/status/{task_id}")
            assert r.status_code == 200
            assert r.get_json()["task_id"] == task_id
