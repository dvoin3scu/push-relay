"""Outgoing HTTP with a single retry on transient failures."""
from __future__ import annotations

import base64
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

log = logging.getLogger("push-relay")

USER_AGENT = "push-relay"


@dataclass
class Response:
    status: int
    body: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


def basic_auth(user: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def _transient(status: int) -> bool:
    return status == 0 or status == 429 or status >= 500


def post_json(url: str, payload: dict, headers: dict | None = None, *,
              timeout: float = 10.0, retry_delay: float = 5.0) -> Response:
    """POST JSON; retry once after retry_delay on network errors, 429 and 5xx."""
    data = json.dumps(payload).encode()
    all_headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT, **(headers or {})}
    response = Response(0, "")
    for attempt in (1, 2):
        request = urllib.request.Request(url, data=data, headers=all_headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                response = Response(resp.status, resp.read().decode(errors="replace"))
        except urllib.error.HTTPError as exc:
            response = Response(exc.code, exc.read().decode(errors="replace"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            response = Response(0, str(exc))
        if response.ok or not _transient(response.status) or attempt == 2:
            return response
        log.warning("POST %s failed (%s), retrying in %ss", url, response.status or response.body, retry_delay)
        time.sleep(retry_delay)
    return response
