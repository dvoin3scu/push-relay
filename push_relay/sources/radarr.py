"""Radarr, and Whisparr v2 (a Radarr fork that calls movies scenes)."""
from __future__ import annotations

from ..text import humanize, join
from .arr import ArrSource, Outcome, Subject, file_line, image_url, seerr_links, source_line
from .base import Context


class RadarrSource(ArrSource):
    name = "radarr"
    noun = "Movie"
    tmdb_links = True

    def _movie(self, payload: dict) -> dict:
        return payload.get("movie") or payload.get("scene") or {}

    def subject(self, payload: dict, ctx: Context) -> Subject:
        movie = self._movie(payload)
        year = movie.get("year")
        return Subject(
            headline=join(movie.get("title"), f"({year})" if year else "", sep=" "),
            image=image_url(movie.get("images"), "poster", "screenshot", "fanart"),
            links=seerr_links("movie", movie.get("tmdbId"), ctx) if self.tmdb_links else [],
        )

    def outcome(self, event_type: str, payload: dict) -> Outcome | None:
        noun = self.noun
        if event_type == "Grab":
            release = payload.get("release") or {}
            return Outcome("grab", "Grabbed", f"{noun} grabbed!",
                           [file_line(release), source_line(payload)])
        if event_type == "Download":
            upgrade = bool(payload.get("isUpgrade"))
            return Outcome("upgrade" if upgrade else "import", "Upgraded" if upgrade else "Imported",
                           f"{noun} {'upgraded' if upgrade else 'imported'} successfully!",
                           [file_line(payload.get("movieFile")), source_line(payload)])
        if event_type == "MovieAdded":
            return Outcome("added", "Added", f"{noun} added")
        if event_type == "MovieDelete":
            return Outcome("deleted", "Deleted", f"{noun} deleted",
                           ["Files deleted" if payload.get("deletedFiles") else ""])
        if event_type == "MovieFileDelete":
            file = payload.get("movieFile") or {}
            return Outcome("file_deleted", "File deleted", f"{noun} file deleted",
                           [file_line(file), humanize(payload.get("deleteReason") or "")])
        if event_type == "Rename":
            return Outcome("rename", "Renamed", f"{noun} files renamed")
        return None


class WhisparrSource(RadarrSource):
    name = "whisparr"
    noun = "Scene"
    tmdb_links = False
