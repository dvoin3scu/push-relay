"""Fallback for /hook/<name> when no adapter exists: best effort, so something always shows up.

*arr-style payloads (eventType) get the shared *arr handling for Test, Health, HealthRestored,
ApplicationUpdate, ManualInteractionRequired and *Failure. Everything else is read from common
field names; when nothing is recognised, the first top-level values are listed.
"""
from __future__ import annotations

from ..model import Event
from ..rules import slug
from ..text import humanize, join
from .arr import ArrSource, image_url
from .base import Context, Source

TITLE_KEYS = ("title", "subject", "name", "headline")
BODY_KEYS = ("message", "body", "text", "description", "content", "msg", "details")
EVENT_KEYS = ("eventType", "event", "type", "notification_type", "status", "action")
IMAGE_KEYS = ("image", "poster", "thumbnail", "thumb", "cover", "image_url", "imageUrl")
MAX_FALLBACK_LINES = 5


def _first(payload: dict, keys) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()
    return ""


def _nested(payload: dict) -> list[dict]:
    return [v for v in payload.values() if isinstance(v, dict)]


def _headline(payload: dict) -> str:
    title = _first(payload, TITLE_KEYS)
    if title:
        return title
    # e.g. {"author": {"name": ...}, "book": {"title": ...}} -> "Author – Book"
    return join(*(_first(d, TITLE_KEYS) for d in _nested(payload)), sep=" – ")


def _image(payload: dict) -> str:
    url = _first(payload, IMAGE_KEYS)
    if url.startswith("http"):
        return url
    for value in _nested(payload) + [payload]:
        url = image_url(value.get("images"), "poster", "cover", "fanart")
        if url:
            return url
    return ""


def _fallback_lines(payload: dict) -> list[str]:
    lines = [f"{key}: {value}" for key, value in payload.items()
             if isinstance(value, (str, int, float, bool)) and str(value).strip()]
    return lines[:MAX_FALLBACK_LINES]


class _ArrShared(ArrSource):
    """Only the events every *arr sends the same way; media events fall through."""

    name = "generic"


class GenericSource(Source):
    name = "generic"

    def __init__(self):
        self._arr = _ArrShared()

    def parse(self, payload: dict, ctx: Context) -> Event | None:
        if payload.get("eventType"):
            event = self._arr.parse(payload, ctx)
            if event is not None:
                return event
        label = humanize(_first(payload, EVENT_KEYS))
        body = _first(payload, BODY_KEYS)
        headline = _headline(payload)
        details = body.splitlines() if body else ([] if headline else _fallback_lines(payload))
        return Event(
            self.name, self.instance(payload, ctx),
            kind="generic", action=slug(label).replace("-", "_") or "info",
            label=label, headline=headline, summary=label or "Notification",
            details=details, image=_image(payload),
        )
