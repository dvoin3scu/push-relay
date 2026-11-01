"""The normalised event every source adapter produces and every notifier consumes."""
from __future__ import annotations

from dataclasses import dataclass, field

SEVERITIES = ("low", "normal", "high", "urgent")


@dataclass
class Link:
    label: str
    url: str


@dataclass
class Event:
    """What happened, independent of where it came from and where it goes.

    source    adapter name (radarr, sonarr, seerr, notify, ...)
    instance  display name of the sending instance (radarr-4k, sonarr-hd, ...)
    kind      template family: media | health | generic
    action    normalised event name used by the severity rules (grab, import, health_error, ...)
    label     short status line (Grabbed, Imported, Health issue, ...)
    headline  what it is about (Drive (2011), Indexer status, ...)
    summary   one sentence (Movie grabbed!, 3 episodes imported successfully!, ...)
    details   extra lines, empty ones are dropped
    group     Bark group / ntfy topic chosen by the sender; otherwise from apps.yaml
    """

    source: str
    instance: str
    kind: str = "generic"
    action: str = "info"
    label: str = ""
    headline: str = ""
    summary: str = ""
    details: list[str] = field(default_factory=list)
    image: str = ""
    url: str = ""
    links: list[Link] = field(default_factory=list)
    emoji: str = ""
    group: str = ""     # set only when the sender chose it (?group=)
    severity: str = ""  # set by the adapter only when the sender chose it (e.g. /notify bark://critical)

    @property
    def body(self) -> str:
        return "\n".join(line for line in self.details if line)
