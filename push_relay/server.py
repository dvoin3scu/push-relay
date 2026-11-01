"""HTTP front end (standard library only)."""
from __future__ import annotations

import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

from . import __version__
from .app import Application, Request
from .config import Settings

log = logging.getLogger("push-relay")

MAX_BODY = 1024 * 1024


def make_handler(app: Application) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = f"push-relay/{__version__}"

        def _serve(self, method: str) -> None:
            url = urlsplit(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                self._reply(413, {"error": "payload too large"})
                return
            request = Request(
                method=method,
                path=url.path,
                query=dict(parse_qsl(url.query)),
                headers={k.lower(): v for k, v in self.headers.items()},
                body=self.rfile.read(length) if length else b"",
            )
            response = app.handle(request)
            self._reply(response.status, response.payload)

        def _reply(self, status: int, payload: dict) -> None:
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            self._serve("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._serve("POST")

        def log_message(self, fmt: str, *args) -> None:
            if not self.path.startswith("/health"):  # keep healthchecks out of the log
                log.debug("%s %s", self.address_string(), fmt % args)

    return Handler


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(),
                        format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    settings = Settings.from_env()
    app = Application(settings)
    for problem in app.problems:
        log.error("config: %s", problem)
    if not settings.token:
        log.warning("config: PUSH_TOKEN is not set, every request is accepted")
    log.info("push-relay %s on :%s, backends: %s", __version__, settings.port,
             ", ".join(n.name for n in app.notifiers) or "none")
    server = ThreadingHTTPServer(("0.0.0.0", settings.port), make_handler(app))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
