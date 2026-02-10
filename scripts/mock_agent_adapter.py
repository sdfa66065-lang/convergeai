#!/usr/bin/env python3
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


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
