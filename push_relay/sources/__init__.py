"""Registry of source adapters, by the name used in /hook/<source>."""
from __future__ import annotations

from .base import Context, PayloadError, Source
from .decypharr import DecypharrSource
from .dispatcharr import DispatcharrSource
from .generic import GenericSource
from .lidarr import LidarrSource
from .notify import NotifySource
from .prowlarr import ProwlarrSource
from .radarr import RadarrSource, WhisparrSource
from .seerr import SeerrSource
from .sonarr import SonarrSource

__all__ = ["Context", "PayloadError", "Source", "SOURCES", "NOTIFY", "GENERIC"]

SOURCES: dict[str, Source] = {
    source.name: source
    for source in (RadarrSource(), WhisparrSource(), SonarrSource(), LidarrSource(),
                   ProwlarrSource(), SeerrSource(), DecypharrSource(), DispatcharrSource())
}
NOTIFY = NotifySource()
GENERIC = GenericSource()  # /hook/<name> without an adapter
