"""Settings read from the environment (the compose .env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path



def _list(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


@dataclass
class BarkSettings:
    server: str = "https://api.day.app"
    device_keys: list[str] = field(default_factory=list)
    key: str = ""
    critical_volume: int = 4
    user: str = ""
    password: str = ""

    @property
    def enabled(self) -> bool:
        return bool(self.device_keys)

    def problem(self) -> str:
        if not self.enabled:
            return ""
        if len(self.key.encode()) not in (16, 24, 32):
            return "BARK_KEY must be 16, 24 or 32 characters"
        return ""


@dataclass
class NtfySettings:
    server: str = "https://ntfy.sh"
    topic: str = ""
    token: str = ""

    @property
    def enabled(self) -> bool:
        return bool(self.topic)

    def problem(self) -> str:
        return ""


@dataclass
class Settings:
    port: int = 8092
    token: str = ""
    config_dir: Path = Path("/config")
    seerr_url: str = ""
    retry_delay: float = 5.0
    timeout: float = 10.0
    bark: BarkSettings = field(default_factory=BarkSettings)
    ntfy: NtfySettings = field(default_factory=NtfySettings)

    @classmethod
    def from_env(cls, env=None) -> "Settings":
        env = os.environ if env is None else env
        get = lambda name, default="": (env.get(name) or default).strip()
        try:
            volume = int(get("BARK_CRITICAL_VOLUME", "4"))
        except ValueError:
            volume = 4
        return cls(
            port=int(get("PUSH_PORT", "8092")),
            token=get("PUSH_TOKEN"),
            config_dir=Path(get("PUSH_CONFIG_DIR", "/config")),
            seerr_url=get("SEERR_URL").rstrip("/"),
            retry_delay=float(get("PUSH_RETRY_DELAY", "5")),
            timeout=float(get("PUSH_TIMEOUT", "10")),
            bark=BarkSettings(
                server=get("BARK_SERVER", "https://api.day.app").rstrip("/"),
                device_keys=_list(get("BARK_DEVICE_KEYS")),
                key=get("BARK_KEY"),
                critical_volume=max(0, min(10, volume)),
                user=get("BARK_USER"),
                password=get("BARK_PASSWORD"),
            ),
            ntfy=NtfySettings(
                server=get("NTFY_SERVER", "https://ntfy.sh").rstrip("/"),
                topic=get("NTFY_TOPIC"),
                token=get("NTFY_TOKEN"),
            ),
        )

    def problems(self) -> list[str]:
        problems = [p for p in (self.bark.problem(), self.ntfy.problem()) if p]
        if not self.bark.enabled and not self.ntfy.enabled:
            problems.append("no backend configured (set BARK_DEVICE_KEYS and/or NTFY_TOPIC)")
        return problems
