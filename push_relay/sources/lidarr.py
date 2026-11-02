"""Lidarr (a tap opens the album on MusicBrainz, or the artist when there is not exactly one album)."""
from __future__ import annotations

from ..text import join, year_of
from .arr import ArrSource, Outcome, Subject, file_line, image_url, source_line
from .base import Context


MUSICBRAINZ = "https://musicbrainz.org"


def musicbrainz_url(albums: list[dict], artist: dict) -> str:
    album_id = albums[0].get("mbId") if len(albums) == 1 else ""
    if album_id:
        return f"{MUSICBRAINZ}/release-group/{album_id}"
    return f"{MUSICBRAINZ}/artist/{artist['mbId']}" if artist.get("mbId") else ""


class LidarrSource(ArrSource):
    name = "lidarr"

    @staticmethod
    def _albums(payload: dict) -> list[dict]:
        albums = payload.get("albums") or []
        if not albums and payload.get("album"):
            albums = [payload["album"]]
        return albums

    def subject(self, payload: dict, ctx: Context) -> Subject:
        artist = payload.get("artist") or {}
        albums = self._albums(payload)
        album = ""
        if len(albums) == 1:
            year = year_of(albums[0].get("releaseDate"))
            album = join(albums[0].get("title"), f"({year})" if year else "", sep=" ")
        elif albums:
            album = f"{len(albums)} albums"
        image = next((url for url in (image_url(a.get("images"), "cover") for a in albums) if url), "")
        return Subject(
            headline=join(artist.get("name"), album, sep=" – "),
            image=image or image_url(artist.get("images"), "poster", "fanart"),
            url=musicbrainz_url(albums, artist),
        )

    def outcome(self, event_type: str, payload: dict) -> Outcome | None:
        if event_type == "Grab":
            return Outcome("grab", "Grabbed", "Album grabbed!",
                           [file_line(payload.get("release"), with_size=True), source_line(payload)])
        if event_type in ("Download", "AlbumDownload"):
            upgrade = bool(payload.get("isUpgrade"))
            tracks = payload.get("trackFiles") or []
            first = tracks[0] if tracks else {}
            count = f"{len(tracks)} tracks" if len(tracks) > 1 else ""
            return Outcome("upgrade" if upgrade else "import", "Upgraded" if upgrade else "Imported",
                           f"Album {'upgraded' if upgrade else 'imported'} successfully!",
                           [join(count, first.get("quality"), first.get("releaseGroup")), source_line(payload)])
        if event_type in ("ArtistAdd", "ArtistAdded"):
            return Outcome("added", "Added", "Artist added")
        if event_type in ("ArtistDelete", "ArtistDeleted"):
            return Outcome("deleted", "Deleted", "Artist deleted")
        if event_type in ("AlbumDelete", "AlbumDeleted"):
            return Outcome("deleted", "Deleted", "Album deleted")
        if event_type == "Rename":
            return Outcome("rename", "Renamed", "Files renamed")
        if event_type in ("Retag", "TrackRetag"):
            return Outcome("retag", "Retagged", "Tracks retagged")
        return None
