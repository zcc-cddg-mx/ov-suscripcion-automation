"""HTTP API listener for the Code Agent (architecture v3).

Exposes three endpoints:

  GET  /health              — liveness check
  POST /run                 — enqueue a migration task (returns 202 immediately)
  GET  /status/<task_id>    — poll task status

POST /run request body:

  Tipo 1 — ren-data:
    {"command": "ren-data", "ticket": "ZNRX-67108",
     "input": "requirements/.../baseticketMES.xlsx",
     "year": 2026, "month": 8,
     "commit": true, "compile": true}

  Tipo 2 — rules:
    {"command": "rules", "ticket": "RITM2500000",
     "input": "data/raw.xlsx", "entity": "VHPlanRules",
     "commit": true, "compile": true}

POST /run response — always 202 Accepted (or 400 on malformed body):
  {"status": "queued",    "task_id": "a1b2c3d4"}
  {"status": "rejected",  "task_id": "a1b2c3d4",
   "active_task": {"task_id": "...", "ticket": "...", "started_at": "..."}}

GET /status/<task_id>:
  {"status": "queued" | "running" | "done" | "error" | "rejected", ...result fields}
"""

from __future__ import annotations

import os
import threading
import traceback
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request

from main import run_payload
from src.build_check import BuildCheckError
from src.config import load_config
from src.logger import log

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Task registry and concurrency control
# ─────────────────────────────────────────────────────────────────────────────
_tasks: dict[str, dict] = {}
_lock = threading.Lock()
_current_task: dict | None = None  # {task_id, ticket, started_at}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "code-agent"})


@app.post("/run")
def run():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"status": "error", "error": "Request body must be JSON"}), 400

    task_id = str(uuid.uuid4())[:8]

    # Concurrency check in the request handler (not the worker thread) so the
    # rejection is instantaneous — no race between thread scheduling and the lock.
    if not _lock.acquire(blocking=False):
        active = _current_task or {}
        log("RECV", (
            f"task_id={task_id} ticket={payload.get('ticket')} REJECTED — "
            f"task {active.get('task_id')} ({active.get('ticket')}) already running"
        ))
        _tasks[task_id] = {
            "status": "rejected",
            "task_id": task_id,
            "error": f"Task {active.get('task_id')} ({active.get('ticket')}) is already running",
            "active_task": active,
        }
        return jsonify({"status": "rejected", "task_id": task_id, "active_task": active}), 202

    # Lock acquired — register task and hand off to worker thread
    _tasks[task_id] = {"status": "queued", "task_id": task_id}
    log("RECV", f"task_id={task_id} ticket={payload.get('ticket')} ACCEPTED — lock acquired")

    def worker():
        global _current_task

        _current_task = {
            "task_id": task_id,
            "ticket": payload.get("ticket"),
            "started_at": _now_iso(),
        }
        _tasks[task_id]["status"] = "running"

        try:
            result = run_payload(payload)
        except BuildCheckError as exc:
            log("ERROR", f"task_id={task_id} build failed: {exc}")
            _tasks[task_id].update({
                "status": "error",
                "error": str(exc),
                "build_status": "failed",
            })
        except (ValueError, KeyError) as exc:
            log("ERROR", f"task_id={task_id} validation error: {exc}")
            _tasks[task_id].update({
                "status": "error",
                "error": str(exc),
                "build_status": None,
            })
        except Exception as exc:
            traceback.print_exc()
            log("ERROR", f"task_id={task_id} unexpected error: {exc}")
            _tasks[task_id].update({
                "status": "error",
                "error": str(exc),
                "build_status": None,
            })
        else:
            cfg = load_config()
            repo_name = os.path.basename(os.path.normpath(cfg.get("repo", "")))
            branch = result.get("branch")
            summary = (
                f"Migration {result['base_name']} generated and pushed to {branch}"
                if branch
                else f"Migration {result['base_name']} generated (no commit)"
            )
            _tasks[task_id].update({
                "status": "done",
                "branch": branch,
                "aux_branch": result.get("aux_branch"),
                "commit_id": result.get("commit_id"),
                "repo": repo_name,
                "build_status": "success" if result.get("commit_id") else None,
                "summary": summary,
            })
        finally:
            _current_task = None
            _lock.release()

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"status": "queued", "task_id": task_id}), 202


@app.get("/status/<task_id>")
def status(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
