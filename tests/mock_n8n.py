"""Mock n8n webhook server for local callback testing.

Receives POST requests from the Code Agent and logs the payload.
Run before starting the agent:

    python tests/mock_n8n.py [--port 9099]

Then set in .env.local:
    export N8N_CALLBACK_URL=http://172.17.0.1:9099/webhook

The server keeps running and prints each received payload.
Press Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer


class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default access log

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok", "service": "mock-n8n"})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        try:
            payload = json.loads(raw)
        except ValueError:
            payload = {"raw": raw.decode(errors="replace")}

        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"\n[{ts}] POST {self.path} — callback received:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))

        status = payload.get("status", "?")
        ticket = payload.get("ticket", "?")
        branch = payload.get("branch", "—")
        print(f"  → ticket={ticket}  status={status}  branch={branch}")

        self._respond(200, {"status": "received"})

    def _respond(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser(description="Mock n8n webhook server")
    parser.add_argument("--port", type=int, default=9099)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), WebhookHandler)
    print(f"Mock n8n listening on http://{args.host}:{args.port}/webhook")
    print(f"Set in .env.local:  export N8N_CALLBACK_URL=http://172.17.0.1:{args.port}/webhook")
    print("Waiting for callbacks... (Ctrl+C to stop)\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
