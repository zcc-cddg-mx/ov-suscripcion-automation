"""HTTP API listener for the Code Agent (architecture v3).

Exposes two endpoints:

  GET  /health   — liveness check; returns {"status": "ok", "service": "code-agent"}
  POST /run      — execute a migration from a JSON payload sent by n8n

POST /run request body (same schema as run-payload CLI):

  Tipo 1 — ren-data:
    {"command": "ren-data", "ticket": "ZNRX-67108",
     "input": "requirements/.../baseticketMES.xlsx",
     "year": 2026, "month": 8, "commit": true}

  Tipo 2 — rules:
    {"command": "rules", "ticket": "RITM2500000",
     "input": "data/raw.xlsx", "entity": "VHPlanRules", "commit": true}

POST /run response (success):
  {"status": "success", "branch": "...", "commit_id": "...",
   "repo": "...", "build_status": null, "summary": "..."}

POST /run response (error):
  {"status": "error", "error": "...", "build_status": null}
"""

from __future__ import annotations

import os
import traceback

from flask import Flask, jsonify, request

from main import run_payload
from src.build_check import BuildCheckError
from src.config import load_config

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "code-agent"})


@app.post("/run")
def run():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"status": "error", "error": "Request body must be JSON"}), 400

    try:
        result = run_payload(payload)
    except BuildCheckError as exc:
        return jsonify({"status": "error", "error": str(exc), "build_status": "failed"}), 422
    except (ValueError, KeyError) as exc:
        return jsonify({"status": "error", "error": str(exc), "build_status": None}), 422
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(exc), "build_status": None}), 500

    cfg = load_config()
    repo_name = os.path.basename(os.path.normpath(cfg.get("repo", "")))

    branch = result.get("branch")
    commit_id = result.get("commit_id")
    summary = (
        f"Migration {result['base_name']} generated and pushed to {branch}"
        if branch
        else f"Migration {result['base_name']} generated (no commit)"
    )

    build_status = "success" if result.get("commit_id") else None

    return jsonify({
        "status": "success",
        "branch": branch,
        "commit_id": commit_id,
        "repo": repo_name,
        "build_status": build_status,
        "summary": summary,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
