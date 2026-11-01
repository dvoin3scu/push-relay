"""Event pipeline: rules -> view -> every enabled notifier."""
from __future__ import annotations

import logging

from .model import Event
from .notifiers import Notifier, Result
from .rules import Rules
from .view import build_view

log = logging.getLogger("push-relay")


class Dispatcher:
    def __init__(self, rules: Rules, notifiers: list[Notifier]):
        self.rules = rules
        self.notifiers = notifiers

    def dispatch(self, event: Event, overrides: dict[str, str] | None = None) -> list[Result]:
        """overrides: profile fields from the request URL, applied over apps.yaml."""
        severity = self.rules.severity(event)
        app = self.rules.app(event.source, event.instance).customised(overrides or {})
        view = build_view(event, app, severity)
        results = []
        for notifier in self.notifiers:
            try:
                result = notifier.send(view)
            except Exception as exc:  # one broken backend or template must not stop the others
                log.exception("%s: failed to send", notifier.name)
                result = Result(notifier.name, False, f"{type(exc).__name__}: {exc}")
            results.append(result)
            log.info("%s %s/%s %s [%s] -> %s %s", event.source, event.instance, event.action, severity,
                     event.headline, result.backend, "ok" if result.ok else f"FAILED {result.detail}")
        return results
