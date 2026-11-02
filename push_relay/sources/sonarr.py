"""Sonarr."""
from __future__ import annotations

from ..text import humanize, join
from .arr import ArrSource, Outcome, Subject, file_line, image_url, seerr_links, source_line
from .base import Context


def episode_range(episodes: list[dict]) -> str:
    """S02E01, S03E01–E08, or S01E10–S02E02 across seasons."""
    pairs = sorted((int(e.get("seasonNumber") or 0), int(e.get("episodeNumber") or 0)) for e in episodes or [])
    if not pairs:
        return ""
    (s1, e1), (s2, e2) = pairs[0], pairs[-1]
    first = f"S{s1:02d}E{e1:02d}"
    if (s1, e1) == (s2, e2):
        return first
    return f"{first}–E{e2:02d}" if s1 == s2 else f"{first}–S{s2:02d}E{e2:02d}"


def episodes_word(count: int) -> str:
    return f"{count} episodes" if count > 1 else "Episode"


class SonarrSource(ArrSource):
    name = "sonarr"

    def subject(self, payload: dict, ctx: Context) -> Subject:
        series = payload.get("series") or {}
        return Subject(
            headline=join(series.get("title"), episode_range(payload.get("episodes")), sep=" – "),
            image=image_url(series.get("images"), "poster", "fanart", "banner"),
            links=seerr_links("tv", series.get("tmdbId"), ctx),
        )

    def outcome(self, event_type: str, payload: dict) -> Outcome | None:
        count = len(payload.get("episodes") or []) or 1
        if event_type == "Grab":
            return Outcome("grab", "Grabbed", f"{episodes_word(count)} grabbed!",
                           [file_line(payload.get("release"), with_size=True), source_line(payload)])
        if event_type in ("Download", "ImportComplete"):
            files = payload.get("episodeFiles")
            if files:  # On Import Complete: one notification for the whole download
                return Outcome("import", "Imported", f"{episodes_word(count)} imported successfully!",
                               [file_line(payload.get("release")), source_line(payload)])
            upgrade = bool(payload.get("isUpgrade"))
            return Outcome("upgrade" if upgrade else "import", "Upgraded" if upgrade else "Imported",
                           f"{episodes_word(count)} {'upgraded' if upgrade else 'imported'} successfully!",
                           [file_line(payload.get("episodeFile")), source_line(payload)])
        if event_type == "SeriesAdd":
            return Outcome("added", "Added", "Series added")
        if event_type == "SeriesDelete":
            return Outcome("deleted", "Deleted", "Series deleted",
                           ["Files deleted" if payload.get("deletedFiles") else ""])
        if event_type == "EpisodeFileDelete":
            return Outcome("file_deleted", "File deleted", "Episode file deleted",
                           [file_line(payload.get("episodeFile")), humanize(payload.get("deleteReason") or "")])
        if event_type == "Rename":
            return Outcome("rename", "Renamed", "Files renamed")
        return None
