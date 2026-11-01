"""Test helpers: sample payloads and a fake push server that records requests."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAYLOADS = Path(__file__).parent / "payloads"


def payload(name: str) -> dict:
    return json.loads((PAYLOADS / f"{name}.json").read_text())


class FakeServer:
    """Records JSON POSTs; answers with the queued statuses, then 200."""

    def __init__(self, statuses=()):
        self.requests: list[tuple[str, dict, dict]] = []
        self.statuses = list(statuses)
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                outer.requests.append((self.path, dict(self.headers), json.loads(body)))
                status = outer.statuses.pop(0) if outer.statuses else 200
                self.send_response(status)
                self.end_headers()
                self.wfile.write(b'{"code":200}')

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
