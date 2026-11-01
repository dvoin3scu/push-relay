"""Severity and per-app presentation rules.

Defaults ship in push_relay/defaults/rules/*.yaml. Files with the same name in
<config>/rules/ are deep-merged on top, so an override only lists what changes.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .model import SEVERITIES, Event

log = logging.getLogger("push-relay")

DEFAULTS_DIR = Path(__file__).parent / "defaults" / "rules"


def _merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def _load(name: str, override_dir: Path | None) -> dict:
    data = yaml.safe_load((DEFAULTS_DIR / name).read_text()) or {}
    if override_dir:
        path = override_dir / name
        if path.is_file():
            try:
                data = _merge(data, yaml.safe_load(path.read_text()) or {})
                log.info("rules: loaded override %s", path)
            except yaml.YAMLError as exc:
                log.error("rules: ignoring invalid %s: %s", path, exc)
    return data


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")


@dataclass
class AppProfile:
    """Presentation settings for one source/instance (from apps.yaml)."""

    name: str = ""
    emoji: str = ""
    tag: str = ""
    icon: str = ""
    tap: str = ""
    group: str = ""


class Rules:
    def __init__(self, config_dir: Path | None = None):
        override_dir = config_dir / "rules" if config_dir else None
        severity = _load("severity.yaml", override_dir)
        self._default = severity.get("default", "normal")
        self._events: dict = severity.get("events") or {}
        self._apps: dict = _load("apps.yaml", override_dir)

    # --- severity -----------------------------------------------------------------------
    def severity(self, event: Event) -> str:
        """Explicit sender choice wins, then the most specific rule."""
        if event.severity in SEVERITIES:
            return event.severity
        keys = (
            f"{event.source}.{slug(event.instance)}.{event.action}",
            f"{event.source}.{event.action}",
            event.action,
        )
        for key in keys:
            value = self._events.get(key)
            if value in SEVERITIES:
                return value
        return self._default if self._default in SEVERITIES else "normal"

    # --- presentation -------------------------------------------------------------------
    def app(self, source: str, instance: str) -> AppProfile:
        entry = dict(self._apps.get("default") or {})
        source_entry = self._apps.get(source) or {}
        instances = source_entry.get("instances") or {}
        entry = _merge(entry, {k: v for k, v in source_entry.items() if k != "instances"})
        for key, value in instances.items():
            if slug(key) == slug(instance):
                entry = _merge(entry, value or {})
                break
        fields = AppProfile.__dataclass_fields__
        return AppProfile(**{k: str(v) for k, v in entry.items() if k in fields and v is not None})
