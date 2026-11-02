"""Shared handling for the *arr Webhook connection (Radarr, Sonarr, Lidarr, Whisparr, Prowlarr).

Events every *arr sends the same way (Test, Health, HealthRestored, ApplicationUpdate,
ManualInteractionRequired, *Failure) are handled here. Each app adapter describes what the
event is about (subject) and its own media events (Grab, Download, ...).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..model import Event, Link
from ..text import humanize, join, size
from .base import Context, PayloadError, Source


@dataclass
class Subject:
    """What a media event is about."""

    headline: str = ""
    image: str = ""
    links: list[Link] = field(default_factory=list)


@dataclass
class Outcome:
    """What happened to the subject."""

    action: str
    label: str
    summary: str
    details: list[str] = field(default_factory=list)


def image_url(images, *cover_types: str) -> str:
    """Public URL of the first image of the given cover types (remoteUrl, else an absolute url)."""
    images = images or []
    for cover_type in cover_types:
        for image in images:
            if (image.get("coverType") or "").lower() == cover_type:
                for key in ("remoteUrl", "url"):
                    url = image.get(key) or ""
                    if url.startswith("http"):
                        return url
    return ""


def file_line(file: dict | None, with_size: bool = False) -> str:
    """'WEBDL-2160p · FLUX', plus the size for grabs ('· 9.0 GB')."""
    file = file or {}
    return join(file.get("quality"), file.get("releaseGroup"), size(file.get("size")) if with_size else "")


def source_line(payload: dict) -> str:
    release = payload.get("release") or {}
    return join(release.get("indexer"), payload.get("downloadClient"))


def check_name(check_type: str) -> str:
    """'IndexerStatusCheck' -> 'Indexer status'."""
    name = humanize(check_type or "")
    if name.lower().endswith(" check"):
        name = name[: -len(" check")]
    return name or "Health"


def seerr_links(kind: str, tmdb_id, ctx: Context) -> list[Link]:
    """TMDB and Seerr pages for a movie/tv TMDB id."""
    if not tmdb_id or str(tmdb_id) == "0":
        return []
    links = [Link("TMDB", f"https://www.themoviedb.org/{kind}/{tmdb_id}")]
    if ctx.seerr_url:
        links.append(Link("Seerr", f"{ctx.seerr_url}/{kind}/{tmdb_id}"))
    return links


class ArrSource(Source):
    """Base adapter; subclasses implement subject() and outcome()."""

    def parse(self, payload: dict, ctx: Context) -> Event | None:
        event_type = payload.get("eventType")
        if not event_type:
            raise PayloadError("missing eventType")
        instance = self.instance(payload, ctx)

        if event_type == "Test":
            return Event(self.name, instance, kind="generic", action="test", emoji="🧪",
                         label="Test", summary=f"Test notification from {instance}")
        if event_type in ("Health", "HealthRestored", "ApplicationUpdate"):
            return self._health(event_type, payload, instance)

        outcome = self._common_outcome(event_type, payload) or self.outcome(event_type, payload)
        if outcome is None:
            return None
        subject = self.subject(payload, ctx)
        return Event(self.name, instance, kind="media", action=outcome.action, label=outcome.label,
                     headline=subject.headline, summary=outcome.summary, details=outcome.details,
                     image=subject.image, links=subject.links)

    # --- implemented by each app ------------------------------------------------------------
    def subject(self, payload: dict, ctx: Context) -> Subject:
        return Subject()

    def outcome(self, event_type: str, payload: dict) -> Outcome | None:
        return None

    # --- shared events ---------------------------------------------------------------------
    def _health(self, event_type: str, payload: dict, instance: str) -> Event:
        message = payload.get("message") or ""
        event = Event(self.name, instance, kind="health", headline=check_name(payload.get("type")))
        if event_type == "Health":
            error = (payload.get("level") or "").lower() == "error"
            event.action, event.emoji = ("health_error", "🚨") if error else ("health_warning", "🚧")
            event.label = "Health error" if error else "Health warning"
            event.details = [message]
            event.url = payload.get("wikiUrl") or ""
        elif event_type == "HealthRestored":
            event.action, event.emoji, event.label = "health_restored", "✅", "Health restored"
            event.details = ["Resolved: " + message.replace("The following issue is now resolved: ", "", 1)]
        else:
            event.action, event.emoji, event.label = "update", "⬆️", "Updated"
            event.headline = "Updated"
            event.details = [join(payload.get("previousVersion"), payload.get("newVersion"), sep=" → ") or message]
        event.summary = event.details[0] if event.details else event.label
        return event

    def _common_outcome(self, event_type: str, payload: dict) -> Outcome | None:
        if event_type == "ManualInteractionRequired":
            info = payload.get("downloadInfo") or {}
            messages = [m for status in payload.get("downloadStatusMessages") or [] for m in status.get("messages") or []]
            return Outcome("manual_interaction", "Manual import needed", "Manual import needed", [
                info.get("quality") or "",
                join(payload.get("downloadClient"), payload.get("downloadStatus")),
                messages[0] if messages else "",
            ])
        if event_type.endswith("Failure"):
            action = "import_failure" if event_type.startswith("Import") else "download_failure"
            label = "Import failed" if action == "import_failure" else "Download failed"
            return Outcome(action, label, label, [payload.get("message") or "", source_line(payload)])
        return None
