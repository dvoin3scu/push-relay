"""Notifier interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..templates import TemplateStore


@dataclass
class Result:
    backend: str
    ok: bool
    detail: str = ""


class Notifier(ABC):
    """Turns a view into one backend's message and delivers it."""

    name: str = ""

    def __init__(self, templates: TemplateStore):
        self.templates = templates

    def message(self, view: dict) -> dict:
        """Render this backend's template with the view plus backend-only fields."""
        return self.templates.render(self.name, view["source"], view["kind"], {**view, **self.extra(view)})

    def extra(self, view: dict) -> dict:
        """Backend-specific view fields (level, priority, ...)."""
        return {}

    @abstractmethod
    def send(self, view: dict) -> Result:
        ...
