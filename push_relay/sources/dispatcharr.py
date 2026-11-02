"""Dispatcharr Connect webhooks (Connect -> New Connection -> Webhook).

Without a payload template Dispatcharr form-encodes the event's fields and leaves out the event
name, so the event is inferred from the fields; a few cannot be told apart (VOD started/stopped,
EPG/M3U blocked). A payload template with an "event" field (see README) makes every event exact.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..model import Event
from ..text import join, size
from .base import Context, Source


@dataclass(frozen=True)
class Kind:
    label: str
    emoji: str = ""
    health: bool = False  # errors and security events: event kind "health" (own group, see apps.yaml)


EVENTS = {
    "channel_start": Kind("Channel started", "▶️"),
    "channel_stop": Kind("Channel stopped", "⏹️"),
    "channel_reconnect": Kind("Channel reconnected", "🔄"),
    "channel_error": Kind("Channel error", "❌", health=True),
    "channel_failover": Kind("Channel failover", "🔀", health=True),
    "stream_switch": Kind("Stream switched", "🔀"),
    "recording_start": Kind("Recording started", "⏺️"),
    "recording_end": Kind("Recording ended", "⏹️"),
    "recording_interrupted": Kind("Recording interrupted", "⚠️"),
    "epg_refresh": Kind("EPG refreshed", "🗓️"),
    "epg_error": Kind("EPG error", "❌", health=True),
    "m3u_refresh": Kind("M3U refreshed", "📋"),
    "m3u_error": Kind("M3U error", "❌", health=True),
    "client_connect": Kind("Client connected", "🔌"),
    "client_disconnect": Kind("Client disconnected", "🔌"),
    "login_failed": Kind("Login failed", "🔐", health=True),
    "epg_blocked": Kind("EPG blocked", "🚫", health=True),
    "m3u_blocked": Kind("M3U blocked", "🚫", health=True),
    "blocked": Kind("EPG/M3U blocked", "🚫", health=True),  # inferred: EPG and M3U look the same
    "vod_start": Kind("VOD started", "🎞️"),
    "vod_stop": Kind("VOD stopped", "🎞️"),
    "vod": Kind("VOD playback", "🎞️"),  # inferred: start and stop look the same
}


def _has(payload: dict, *keys) -> bool:
    return any(str(payload.get(k) or "").strip() for k in keys)


def infer(payload: dict) -> str:
    """Event name from the fields alone (no template); Dispatcharr drops empty fields before sending."""
    if _has(payload, "recording_id"):
        return "recording_end" if _has(payload, "interrupted", "bytes_written", "end_time", "outcome", "file_name") \
            else "recording_start"
    if _has(payload, "content_name", "content_uuid"):
        return "vod"
    if _has(payload, "account_name"):
        return "m3u_error" if _has(payload, "message") else "m3u_refresh"
    if _has(payload, "source_name"):
        return "epg_error" if _has(payload, "message") else "epg_refresh"
    if _has(payload, "reason") and not _has(payload, "channel_name"):
        return "blocked" if _has(payload, "profile") else "login_failed"
    if _has(payload, "client_id"):
        return "client_disconnect" if _has(payload, "duration", "bytes_sent") else "client_connect"
    if _has(payload, "attempt", "max_attempts"):
        return "channel_reconnect"
    if _has(payload, "error_type", "error_message"):
        return "channel_error"
    if _has(payload, "new_url"):
        return "stream_switch"
    if _has(payload, "reason"):
        return "channel_failover"
    if _has(payload, "runtime", "total_bytes"):
        return "channel_stop"
    if _has(payload, "channel_name"):
        return "channel_start"
    return ""


def _truthy(value) -> bool:
    return str(value or "").strip().lower() in ("true", "1", "yes")


def _seconds(value) -> str:
    try:
        total = int(float(value))
    except (TypeError, ValueError):
        return ""
    hours, rest = divmod(total, 3600)
    return f"{hours}h{rest // 60:02d}m" if hours else f"{rest // 60}m{rest % 60:02d}s"


class DispatcharrSource(Source):
    name = "dispatcharr"

    def parse(self, payload: dict, ctx: Context) -> Event | None:
        action = str(payload.get("event") or "").strip().lower() or infer(payload)
        if action == "recording_end" and _truthy(payload.get("interrupted")):
            action = "recording_interrupted"
        kind = EVENTS.get(action) or Kind(action.replace("_", " ").capitalize() or "Event")
        get = lambda key: str(payload.get(key) or "").strip()  # noqa: E731
        who = join(get("username") or get("user"), get("client_ip"))
        return Event(
            self.name, self.instance(payload, ctx),
            kind="health" if kind.health else "generic",
            action=action or "event", label=kind.label, summary=kind.label, emoji=kind.emoji,
            headline=get("channel_name") or get("content_name") or get("account_name") or get("source_name")
            or get("user") or get("client_ip") or kind.label,
            details=[
                join(get("stream_name"), get("provider_name")),
                get("message"), get("error_message"), get("reason"),
                join(_seconds(get("runtime") or get("duration")), size(get("total_bytes") or get("bytes_written"))),
                join(f"Profile {get('profile')}" if get("profile") and get("profile") != "all" else "", who),
            ],
        )
