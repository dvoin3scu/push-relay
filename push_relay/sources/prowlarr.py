"""Prowlarr: health and update events (shared), plus On Grab."""
from __future__ import annotations

from ..model import Event
from ..text import join, size
from .arr import ArrSource
from .base import Context


class ProwlarrSource(ArrSource):
    name = "prowlarr"

    def parse(self, payload: dict, ctx: Context) -> Event | None:
        if payload.get("eventType") != "Grab":
            return super().parse(payload, ctx)
        release = payload.get("release") or {}
        return Event(self.name, self.instance(payload, ctx), kind="generic", action="grab",
                     label="Grabbed", headline=release.get("releaseTitle") or "Release",
                     summary="Release grabbed!",
                     details=[join(release.get("indexer"), size(release.get("size"))),
                              join(payload.get("source"), payload.get("host"))])
