"""Bark with end-to-end encryption (AES-GCM, fresh IV per device and message)."""
from __future__ import annotations

import base64
import json
import secrets
import string

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import BarkSettings
from ..http import basic_auth, post_json
from ..templates import TemplateStore
from .base import Notifier, Result

LEVELS = {"low": "passive", "normal": "active", "high": "timeSensitive", "urgent": "critical"}
_IV_ALPHABET = string.ascii_letters + string.digits


def new_iv() -> str:
    """12 printable characters, as the Bark app expects (it reads the IV as UTF-8)."""
    return "".join(secrets.choice(_IV_ALPHABET) for _ in range(12))


def encrypt(message: dict, key: str, iv: str) -> str:
    """base64(ciphertext + tag) of the JSON message."""
    plaintext = json.dumps(message, ensure_ascii=False).encode()
    return base64.b64encode(AESGCM(key.encode()).encrypt(iv.encode(), plaintext, None)).decode()


class BarkNotifier(Notifier):
    name = "bark"

    def __init__(self, settings: BarkSettings, templates: TemplateStore, *, timeout: float, retry_delay: float):
        super().__init__(templates)
        self.settings = settings
        self.timeout = timeout
        self.retry_delay = retry_delay

    def extra(self, view: dict) -> dict:
        level = LEVELS.get(view["severity"], "active")
        return {"level": level, "volume": self.settings.critical_volume if level == "critical" else ""}

    def send(self, view: dict) -> Result:
        message = self.message(view)
        headers = {}
        if self.settings.user:
            headers["Authorization"] = basic_auth(self.settings.user, self.settings.password)
        failures = []
        for device_key in self.settings.device_keys:
            iv = new_iv()
            payload = {"device_key": device_key, "ciphertext": encrypt(message, self.settings.key, iv), "iv": iv}
            response = post_json(f"{self.settings.server}/push", payload, headers,
                                 timeout=self.timeout, retry_delay=self.retry_delay)
            if not response.ok:
                failures.append(f"{device_key[:4]}…: HTTP {response.status} {response.body[:120]}")
        sent = len(self.settings.device_keys) - len(failures)
        return Result(self.name, sent > 0, "; ".join(failures) or f"{sent} device(s)")
