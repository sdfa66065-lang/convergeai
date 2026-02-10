#!/usr/bin/env python3
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional


class MockAgentHandler(BaseHTTPRequestHandler):
    server_version = "MockAgentAdapter/0.1"

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b""
        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except json.JSONDecodeError:
            self._send_response(400, {"error": "invalid JSON"})
            return

        configured = _load_preset_response()
        if configured is not None:
            self._send_response(200, configured)
            return

        if all(key in payload for key in ("base", "ours", "theirs")):
            response = {
                "resolved_text": payload.get("ours", ""),
                "confidence": 0.5,
                "resolution": "mock",
            }
        else:
            response = {
                "error": "mock adapter does not generate patches",
                "patch": "",
            }
        self._send_response(200, response)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_response(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _load_preset_response() -> Optional[Dict[str, Any]]:
    response_file = os.getenv("MOCK_ADAPTER_RESPONSE_FILE", "").strip()
    if response_file:
        file_path = Path(response_file)
        loaded = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("MOCK_ADAPTER_RESPONSE_FILE must contain a JSON object")
        return loaded

    resolved_text = os.getenv("MOCK_ADAPTER_RESOLVED_TEXT")
    if resolved_text is not None:
        confidence = float(os.getenv("MOCK_ADAPTER_CONFIDENCE", "0.5"))
        return {
            "resolved_text": resolved_text,
            "confidence": confidence,
            "resolution": "mock-preset",
        }

    patch = os.getenv("MOCK_ADAPTER_PATCH")
    if patch is not None:
        return {"patch": patch}

    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a mock Phase 2 agent adapter.")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8001, help="Port to listen on.")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), MockAgentHandler)
    print(f"Mock agent adapter listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
