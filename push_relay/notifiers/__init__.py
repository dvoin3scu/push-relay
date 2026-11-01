"""Backends, enabled by the presence of their settings."""
from __future__ import annotations

from ..config import Settings
from ..templates import TemplateStore
from .bark import BarkNotifier
from .base import Notifier, Result
from .ntfy import NtfyNotifier

__all__ = ["Notifier", "Result", "build_notifiers"]


def build_notifiers(settings: Settings, templates: TemplateStore) -> list[Notifier]:
    common = {"timeout": settings.timeout, "retry_delay": settings.retry_delay}
    notifiers: list[Notifier] = []
    if settings.bark.enabled and not settings.bark.problem():
        notifiers.append(BarkNotifier(settings.bark, templates, **common))
    if settings.ntfy.enabled and not settings.ntfy.problem():
        notifiers.append(NtfyNotifier(settings.ntfy, templates, **common))
    return notifiers
