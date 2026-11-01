"""Decypharr notifications callback (config.json: notifications.callback_url)."""
from __future__ import annotations

from ..model import Event
from ..text import humanize, join
from .base import Context, PayloadError, Source


class DecypharrSource(Source):
    name = "decypharr"

    def parse(self, payload: dict, ctx: Context) -> Event | None:
        event = payload.get("event")
        if not event:
            raise PayloadError("missing event")
        label = humanize(event)  # download_complete -> Download complete
        failed = "fail" in event or (payload.get("status") or "").lower() in ("error", "failed")
        return Event(
            self.name, self.instance(payload, ctx),
            kind="generic", action=event, label=label,
            headline=payload.get("name") or label,
            summary=label,
            details=[payload.get("message") or "", payload.get("error") or "",
                     join(payload.get("category"), payload.get("debrid"))],
            emoji="❌" if failed else "",
        )
