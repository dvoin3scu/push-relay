"""ntfy JSON publishing (https://docs.ntfy.sh/publish/#publish-as-json)."""
from __future__ import annotations

from ..config import NtfySettings
from ..http import post_json
from ..rules import slug
from ..templates import TemplateStore
from .base import Notifier, Result

PRIORITIES = {"low": 2, "normal": 3, "high": 4, "urgent": 5}


class NtfyNotifier(Notifier):
    name = "ntfy"

    def __init__(self, settings: NtfySettings, templates: TemplateStore, *, timeout: float, retry_delay: float):
        super().__init__(templates)
        self.settings = settings
        self.timeout = timeout
        self.retry_delay = retry_delay

    def extra(self, view: dict) -> dict:
        return {
            "priority": PRIORITIES.get(view["severity"], 3),
            "tags": [view["tag"]] if view.get("tag") else [],
            "markdown_flag": True if view.get("markdown") else None,
            "actions": [{"action": "view", "label": link["label"], "url": link["url"]}
                        for link in view.get("links", [])][:3],  # ntfy allows 3 actions
        }

    def send(self, view: dict) -> Result:
        message = {"topic": slug(view["group"])[:64], **self.message(view)}
        headers = {"Authorization": f"Bearer {self.settings.token}"} if self.settings.token else {}
        response = post_json(self.settings.server, message, headers,
                             timeout=self.timeout, retry_delay=self.retry_delay)
        return Result(self.name, response.ok, f"HTTP {response.status}" + ("" if response.ok else f" {response.body[:120]}"))
