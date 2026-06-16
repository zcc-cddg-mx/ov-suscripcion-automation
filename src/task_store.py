"""SQLite-backed task store for the Code Agent HTTP API.

All task state is persisted to a SQLite database so it survives container restarts.
DB path defaults to /data/tasks.db — override with TASKS_DB env var.
Mount /data as a Docker volume to keep history across image rebuilds.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

_DB_PATH = Path(os.environ.get("TASKS_DB", "/data/tasks.db"))
_lock = threading.Lock()

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id      TEXT PRIMARY KEY,
    ticket       TEXT,
    status       TEXT NOT NULL,
    command      TEXT,
    input_path   TEXT,
    branch       TEXT,
    aux_branch   TEXT,
    commit_id    TEXT,
    repo         TEXT,
    build_status TEXT,
    summary      TEXT,
    error        TEXT,
    active_task  TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
)
"""

_JSON_FIELDS = {"active_task"}
_ALL_FIELDS = [
    "task_id", "ticket", "status", "command", "input_path",
    "branch", "aux_branch", "commit_id", "repo",
    "build_status", "summary", "error", "active_task",
    "created_at", "updated_at",
]


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _lock, _connect() as conn:
        conn.execute(_CREATE_TABLE)


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for field in _JSON_FIELDS:
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except (ValueError, TypeError):
                pass
    return {k: v for k, v in d.items() if v is not None}


def upsert(task: dict, now_iso: str) -> None:
    """Insert or update a task record."""
    row = {f: task.get(f) for f in _ALL_FIELDS}
    row["task_id"] = task["task_id"]
    row["status"] = task["status"]
    row["updated_at"] = now_iso
    if "created_at" not in task:
        row["created_at"] = now_iso

    for field in _JSON_FIELDS:
        if isinstance(row.get(field), dict):
            row[field] = json.dumps(row[field])

    cols = ", ".join(row.keys())
    placeholders = ", ".join(f":{k}" for k in row.keys())
    updates = ", ".join(
        f"{k} = :{k}" for k in row.keys() if k not in ("task_id", "created_at")
    )
    sql = (
        f"INSERT INTO tasks ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(task_id) DO UPDATE SET {updates}"
    )
    with _lock, _connect() as conn:
        conn.execute(sql, row)


def get(task_id: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_recent(limit: int = 50) -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]
