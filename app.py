"""HTTP API listener for the Code Agent (architecture v3).

Exposes four endpoints:

  GET  /health              — liveness check
  POST /run                 — enqueue a migration task (returns 202 immediately)
  GET  /status/<task_id>    — poll task status
  GET  /tasks               — list recent tasks (last 50, newest first)

POST /run — multipart/form-data:

  Tipo 1 — ren-data (archivo Excel adjunto):
    file     = <baseticketMES.xlsx>
    command  = ren-data
    ticket   = ZNRX-67108
    year     = 2026
    month    = 8
    commit   = true
    compile  = true

  Tipo 2 — rules (archivo Excel adjunto):
    file     = <Cotizador_Motor.xlsx>
    command  = rules
    ticket   = RITM2500000
    entity   = VHDriversAge
    commit   = true
    compile  = true

  El archivo recibido se guarda en /data/uploads/<ticket>_<timestamp>_<filename>
  antes de encolar la tarea. La ruta queda registrada en SQLite (input_path).

POST /run response — always 202 Accepted (or 400 on malformed body):
  {"status": "queued",    "task_id": "a1b2c3d4"}
  {"status": "rejected",  "task_id": "a1b2c3d4",
   "active_task": {"task_id": "...", "ticket": "...", "started_at": "..."}}

GET /status/<task_id>:
  {"status": "queued" | "running" | "done" | "error" | "rejected", ...result fields}

Task state is persisted in SQLite (TASKS_DB env var, default /data/tasks.db).
Mount /data as a Docker volume to keep history across container restarts.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests as http_requests
from flask import Flask, jsonify, request

_UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", "/data/uploads"))
_N8N_CALLBACK_URL = os.environ.get("N8N_CALLBACK_URL", "")  # e.g. https://n8n.host/webhook/code-agent-done
# CALLBACK_VERIFY_SSL: "false" desactiva verificación TLS; path a un bundle .pem lo usa como CA
_raw_verify = os.environ.get("CALLBACK_VERIFY_SSL", "true").strip()
_N8N_CALLBACK_VERIFY: bool | str = (
    False if _raw_verify.lower() == "false"
    else True if _raw_verify.lower() == "true"
    else _raw_verify  # path a bundle CA personalizado
)

from main import run_payload
from src.build_check import BuildCheckError
from src.config import load_config
from src.logger import log
from src import task_store

app = Flask(__name__)
task_store.init_db()

_RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "90"))
task_store.cleanup_old_records(days=_RETENTION_DAYS)
task_store.cleanup_old_uploads(_UPLOADS_DIR, days=_RETENTION_DAYS)

# ─────────────────────────────────────────────────────────────────────────────
# Concurrency control
# ─────────────────────────────────────────────────────────────────────────────
_lock = threading.Lock()
_current_task: dict | None = None  # {task_id, ticket, started_at}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_N8N_CALLBACK_RETRIES = 3
_N8N_CALLBACK_BACKOFF_BASE = 2  # seconds — attempts: 2s, 4s, 8s


def _notify_n8n(task: dict) -> None:
    """POST task result to N8N_CALLBACK_URL with up to 3 retries (exponential backoff).

    Logs and swallows errors after all retries — never blocks the worker.
    Body sent to n8n:
      {"ticket": "ZNRX-67108", "status": "success"|"error",
       "branch": "feature/...", "aux_branch": "feature/..._developer_auxiliar",
       "commit_id": "abc123", "summary": "...", "error": "..."}
    """
    if not _N8N_CALLBACK_URL:
        return
    body = {
        "ticket":       task.get("ticket"),
        "status":       "success" if task.get("status") == "done" else "error",
        "task_id":      task.get("task_id"),
        "command":      task.get("command"),
        "branch":       task.get("branch"),
        "aux_branch":   task.get("aux_branch"),
        "commit_id":    task.get("commit_id"),
        "repo":         task.get("repo"),
        "build_status": task.get("build_status"),
        "summary":      task.get("summary"),
        "error":        task.get("error"),
        "completed_at": _now_iso(),
    }
    body = {k: v for k, v in body.items() if v is not None}
    log("N8N", f"callback payload → {json.dumps(body, ensure_ascii=False)}")

    for attempt in range(1, _N8N_CALLBACK_RETRIES + 1):
        try:
            resp = http_requests.post(_N8N_CALLBACK_URL, json=body, timeout=10, verify=_N8N_CALLBACK_VERIFY)
            log("N8N", f"callback → {_N8N_CALLBACK_URL} status={resp.status_code} (attempt {attempt})")
            return
        except Exception as exc:
            if attempt < _N8N_CALLBACK_RETRIES:
                delay = _N8N_CALLBACK_BACKOFF_BASE ** attempt
                log("N8N", f"callback attempt {attempt} failed ({exc}) — retrying in {delay}s")
                time.sleep(delay)
            else:
                log("N8N", f"callback failed after {_N8N_CALLBACK_RETRIES} attempts ({exc}) — task persisted in SQLite")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "code-agent"})


_REQUIRED_COMMON = ("file", "command", "ticket")
_REQUIRED_BY_COMMAND = {
    "ren-data": ("year", "month"),
    "rules":    ("entity",),
}


def _parse_request() -> tuple[dict, str]:
    """Parse multipart/form-data request, validate required fields, save uploaded file.

    Common required fields: file, command, ticket.
    ren-data also requires: year, month.
    rules    also requires: entity.
    Raises ValueError with a descriptive message if any are missing.
    Returns (payload_dict, input_path).
    """
    if not (request.content_type and request.content_type.startswith("multipart/form-data")):
        raise ValueError("Content-Type must be multipart/form-data")

    payload = {k: v for k, v in request.form.items()}

    # Validate common required fields first
    missing = []
    for field in _REQUIRED_COMMON:
        if field == "file":
            f = request.files.get("file")
            if not f or not f.filename:
                missing.append("file")
        elif not payload.get(field):
            missing.append(field)

    # Validate command-specific required fields
    command = payload.get("command", "")
    for field in _REQUIRED_BY_COMMAND.get(command, ()):
        if not payload.get(field):
            missing.append(field)

    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")

    # Coerce numeric and boolean fields — only when present
    for field in ("year", "month"):
        if payload.get(field):
            payload[field] = int(payload[field])
    for field in ("commit", "compile"):
        if field in payload:
            payload[field] = payload[field].lower() in ("true", "1", "yes")

    # Save uploaded file
    file = request.files["file"]
    _UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    ticket_safe = re.sub(r"[^A-Za-z0-9_-]", "_", payload["ticket"])
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(file.filename).name)
    dest = _UPLOADS_DIR / f"{ticket_safe}_{timestamp}_{safe_name}"
    file.save(str(dest))
    log("RECV", f"file saved → {dest.name}")

    payload["input"] = str(dest)
    payload["password"] = request.form.get("password")  # None si no viene
    return payload, str(dest)


@app.post("/run")
def run():
    try:
        payload, input_path = _parse_request()
    except ValueError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400

    task_id = str(uuid.uuid4())[:8]
    now = _now_iso()

    # Concurrency check in the request handler (not the worker thread) so the
    # rejection is instantaneous — no race between thread scheduling and the lock.
    if not _lock.acquire(blocking=False):
        active = _current_task or {}
        log("RECV", (
            f"task_id={task_id} ticket={payload.get('ticket')} REJECTED — "
            f"task {active.get('task_id')} ({active.get('ticket')}) already running"
        ))
        task = {
            "task_id": task_id,
            "ticket": payload.get("ticket"),
            "command": payload.get("command"),
            "input_path": input_path,
            "status": "rejected",
            "error": f"Task {active.get('task_id')} ({active.get('ticket')}) is already running",
            "active_task": active,
            "created_at": now,
        }
        task_store.upsert(task, now)
        return jsonify({"status": "rejected", "task_id": task_id, "active_task": active}), 202

    # Lock acquired — register task and hand off to worker thread
    task = {
        "task_id": task_id,
        "ticket": payload.get("ticket"),
        "command": payload.get("command"),
        "input_path": input_path,
        "status": "queued",
        "created_at": now,
    }
    task_store.upsert(task, now)
    log("RECV", f"task_id={task_id} ticket={payload.get('ticket')} ACCEPTED — lock acquired")

    def worker():
        global _current_task

        _current_task = {
            "task_id": task_id,
            "ticket": payload.get("ticket"),
            "started_at": _now_iso(),
        }
        task_store.upsert({"task_id": task_id, "status": "running"}, _now_iso())

        try:
            result = run_payload(payload)
        except BuildCheckError as exc:
            log("ERROR", f"task_id={task_id} build failed: {exc}")
            task_store.upsert({
                "task_id": task_id,
                "status": "error",
                "error": str(exc),
                "build_status": "failed",
            }, _now_iso())
        except (ValueError, KeyError) as exc:
            log("ERROR", f"task_id={task_id} validation error: {exc}")
            task_store.upsert({
                "task_id": task_id,
                "status": "error",
                "error": str(exc),
            }, _now_iso())
        except Exception as exc:
            traceback.print_exc()
            log("ERROR", f"task_id={task_id} unexpected error: {exc}")
            task_store.upsert({
                "task_id": task_id,
                "status": "error",
                "error": str(exc),
            }, _now_iso())
        else:
            cfg = load_config()
            repo_name = os.path.basename(os.path.normpath(cfg.get("repo", "")))
            branch = result.get("branch")
            summary = (
                f"Migration {result['base_name']} generated and pushed to {branch}"
                if branch
                else f"Migration {result['base_name']} generated (no commit)"
            )
            task_store.upsert({
                "task_id": task_id,
                "status": "done",
                "branch": branch,
                "aux_branch": result.get("aux_branch"),
                "commit_id": result.get("commit_id"),
                "repo": repo_name,
                "build_status": "success" if result.get("commit_id") else None,
                "summary": summary,
            }, _now_iso())
        finally:
            _current_task = None
            _lock.release()
            _notify_n8n(task_store.get(task_id) or {"task_id": task_id, "status": "error"})

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"status": "queued", "task_id": task_id}), 202


@app.get("/status/<task_id>")
def status(task_id: str):
    task = task_store.get(task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.get("/tasks")
def tasks():
    limit = min(int(request.args.get("limit", 50)), 200)
    return jsonify(task_store.get_recent(limit))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
