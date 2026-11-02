"""Request handling, independent of the HTTP server (easy to test)."""
from __future__ import annotations

import hmac
import json
import logging
from dataclasses import dataclass, field
from urllib.parse import parse_qs

from . import __version__
from .config import Settings
from .dispatcher import Dispatcher
from .model import Event, to_severity
from .notifiers import build_notifiers
from .rules import CUSTOMISABLE, Rules
from .sources import GENERIC, NOTIFY, SOURCES, Context, PayloadError
from .templates import TemplateStore

log = logging.getLogger("push-relay")


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)  # lower-case names
    body: bytes = b""


@dataclass
class Response:
    status: int
    payload: dict


class Application:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.templates = TemplateStore(settings.config_dir)
        self.rules = Rules(settings.config_dir)
        self.notifiers = build_notifiers(settings, self.templates)
        self.dispatcher = Dispatcher(self.rules, self.notifiers)
        self.problems = settings.problems()

    # --- routing ---------------------------------------------------------------------------
    def handle(self, request: Request) -> Response:
        parts = [p for p in request.path.split("/") if p]
        if request.method == "GET" and parts == ["health"]:
            return self.health()
        if request.method != "POST" or not parts or parts[0] not in ("hook", "notify"):
            log.warning("%s %s: not found", request.method, request.path)
            return Response(404, {"error": "not found"})
        if not self._authorised(request):
            log.warning("%s %s: invalid or missing token", request.method, request.path)
            return Response(401, {"error": "invalid token"})
        if parts[0] == "hook" and len(parts) == 2:
            return self.hook(parts[1], request)
        if parts[0] == "notify" and len(parts) <= 2:
            return self.notify(parts[1] if len(parts) == 2 else "", request)
        log.warning("%s %s: not found", request.method, request.path)
        return Response(404, {"error": "not found"})

    # --- endpoints -------------------------------------------------------------------------
    def health(self) -> Response:
        if self.problems:
            return Response(503, {"status": "error", "problems": self.problems})
        return Response(200, {"status": "ok", "version": __version__,
                              "backends": [n.name for n in self.notifiers]})

    def hook(self, source_name: str, request: Request) -> Response:
        source = SOURCES.get(source_name)
        if source is None:
            log.info("%s: no adapter, using the generic one", source_name)
            source = GENERIC
        try:
            payload = json.loads(request.body or b"{}")
            if not isinstance(payload, dict):
                raise PayloadError("payload is not a JSON object")
            event = source.parse(payload, self._context(request.query.get("instance", ""), source_name))
        except (ValueError, PayloadError) as exc:
            log.warning("%s: rejected payload: %s", source_name, exc)
            return Response(400, {"error": str(exc)})
        if event is None:
            log.info("%s: ignored event %s", source_name, payload.get("eventType") or "")
            return Response(200, {"status": "ignored"})
        event.source = source_name  # rules and apps.yaml see the name from the URL (also for the generic adapter)
        results = self.dispatcher.dispatch(event, self._customise(event, request.query))
        sent = [r.backend for r in results if r.ok]
        body = {"status": "sent" if sent else "failed", "sent": sent,
                "failed": {r.backend: r.detail for r in results if not r.ok}}
        return Response(200 if sent else 502, body)

    def notify(self, key: str, request: Request) -> Response:
        """Apprise API emulation; always answers 200 so the sender never retries or disables us."""
        try:
            payload = self._apprise_payload(request)
            event = NOTIFY.parse(payload, self._context(key or request.query.get("instance", "")))
            results = self.dispatcher.dispatch(event, self._customise(event, request.query))
            ok = any(r.ok for r in results)
        except ValueError as exc:
            log.warning("notify: rejected payload: %s", exc)
            ok = False
        except Exception:  # noqa: BLE001 - never fail the sender
            log.exception("notify: failed to handle request")
            ok = False
        return Response(200, {"success": ok})

    # --- helpers ---------------------------------------------------------------------------
    @staticmethod
    def _customise(event: Event, query: dict[str, str]) -> dict[str, str]:
        """Apply ?group=, ?level= and ?tap= to the event; return the profile overrides (?emoji=, ?icon=, ...).

        The request URL wins over anything from the payload and apps.yaml.
        """
        event.group = query.get("group") or event.group
        event.url = query.get("tap") or event.url
        event.severity = to_severity(query.get("level", "")) or event.severity
        return {key: query[key] for key in CUSTOMISABLE if query.get(key)}

    def _context(self, instance: str, source: str = "") -> Context:
        return Context(instance=instance, source=source, seerr_url=self.settings.seerr_url)

    def _authorised(self, request: Request) -> bool:
        expected = self.settings.token
        if not expected:
            return True
        auth = request.headers.get("authorization", "")
        given = (request.query.get("token")
                 or request.headers.get("x-push-token")
                 or (auth[7:] if auth.lower().startswith("bearer ") else ""))
        return hmac.compare_digest(given.encode(), expected.encode())

    @staticmethod
    def _apprise_payload(request: Request) -> dict:
        content_type = request.headers.get("content-type", "")
        text = request.body.decode(errors="replace")
        if "application/x-www-form-urlencoded" in content_type:
            return {k: v[-1] for k, v in parse_qs(text).items()}
        payload = json.loads(text or "{}")
        return payload if isinstance(payload, dict) else {}
