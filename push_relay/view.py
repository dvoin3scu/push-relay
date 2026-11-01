"""Builds the backend-neutral view a template is rendered with."""
from __future__ import annotations

from .model import Event
from .rules import AppProfile


def build_view(event: Event, app: AppProfile, severity: str) -> dict:
    instance = app.name or event.instance
    return {
        "source": event.source,
        "instance": instance,
        "kind": event.kind,
        "action": event.action,
        "severity": severity,
        "emoji": event.emoji or app.emoji,
        "label": event.label,
        "headline": event.headline,
        "summary": event.summary,
        "body": event.body,
        "image": event.image,
        "url": event.url or app.tap,
        "icon": app.icon,
        "group": app.group or instance,
        "tag": app.tag,
        "links": [{"label": link.label, "url": link.url} for link in event.links if link.url],
    }
