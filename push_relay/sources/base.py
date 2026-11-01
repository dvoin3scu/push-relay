"""Source adapter interface: one per sender, payload in, Event out."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..model import Event


class PayloadError(ValueError):
    """The payload is not what this source sends."""


@dataclass
class Context:
    """Request details an adapter may need."""

    instance: str          # from ?instance= (may be empty)
    seerr_url: str = ""    # base URL for "open in Seerr" links


class Source(ABC):
    name: str = ""

    @abstractmethod
    def parse(self, payload: dict, ctx: Context) -> Event | None:
        """Return the event, or None when the event is deliberately ignored."""

    def instance(self, payload: dict, ctx: Context) -> str:
        return ctx.instance or str(payload.get("instanceName") or "") or self.name
