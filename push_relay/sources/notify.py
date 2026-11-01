"""Apprise API emulation (POST /notify[/<key>]) for apps that only speak Apprise.

Apprise API stateless payload: {urls, title, body, type, format, tag}. The level comes from the
URL the app was given (bark://timeSensitive, bark://critical, ntfy://high, ...) or from the tag;
otherwise from the type (info/success -> normal, warning/failure -> high).
The group can also travel with the payload: a "group" field (Apprise json:// with -group=...) or
a group= parameter on one of the URLs (bark://timeSensitive?group=network).
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from ..model import Event, to_severity
from ..text import strip_markup
from .base import Context, Source

TYPE_EMOJI = {"warning": "⚠️", "failure": "❌"}


def _words(value) -> list[str]:
    if isinstance(value, (list, tuple)):
        value = " ".join(str(v) for v in value)
    return [w for w in re.split(r"[\s,;]+", str(value or "")) if w]


def level_from(urls, tags) -> str:
    """bark://timeSensitive, barks://host/key?level=critical, ntfy://topic?priority=high, or a tag."""
    for url in _words(urls):
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        candidates = [parts.netloc, *parts.path.split("/"), *query.get("level", []), *query.get("priority", [])]
        for candidate in candidates:
            severity = to_severity(candidate)
            if severity:
                return severity
    for tag in _words(tags):
        severity = to_severity(tag)
        if severity:
            return severity
    return ""


def group_from(payload: dict) -> str:
    if payload.get("group"):
        return str(payload["group"])
    for url in _words(payload.get("urls")):
        group = parse_qs(urlsplit(url).query).get("group")
        if group:
            return group[0]
    return ""


class NotifySource(Source):
    name = "notify"

    def parse(self, payload: dict, ctx: Context) -> Event | None:
        kind = str(payload.get("type") or "info").lower()
        fmt = str(payload.get("format") or "text").lower()
        body = strip_markup(str(payload.get("body") or payload.get("message") or ""), fmt)
        title = strip_markup(str(payload.get("title") or ""), fmt)
        return Event(
            self.name, self.instance(payload, ctx),
            kind="generic", action=kind if kind in ("info", "success", "warning", "failure") else "info",
            headline=title,
            details=body.splitlines(),
            emoji=TYPE_EMOJI.get(kind, ""),
            group=group_from(payload),
            severity=level_from(payload.get("urls"), payload.get("tag") or payload.get("tags")),
        )
