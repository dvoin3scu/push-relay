"""Seerr (Jellyseerr/Overseerr) Webhook agent with the default JSON payload template."""
from __future__ import annotations

from ..model import Event
from ..text import humanize, join
from .arr import seerr_links
from .base import Context, PayloadError, Source

# notification_type -> (action, label)
TYPES = {
    "MEDIA_PENDING": ("request_pending", "Pending approval"),
    "MEDIA_AUTO_REQUESTED": ("request_auto_requested", "Auto requested"),
    "MEDIA_APPROVED": ("request_approved", "Approved"),
    "MEDIA_AUTO_APPROVED": ("request_auto_approved", "Auto approved"),
    "MEDIA_AVAILABLE": ("request_available", "Available"),
    "MEDIA_DECLINED": ("request_declined", "Declined"),
    "MEDIA_FAILED": ("request_failed", "Failed"),
    "ISSUE_CREATED": ("issue_created", "Issue reported"),
    "ISSUE_COMMENT": ("issue_comment", "New comment"),
    "ISSUE_RESOLVED": ("issue_resolved", "Issue resolved"),
    "ISSUE_REOPENED": ("issue_reopened", "Issue reopened"),
    "TEST_NOTIFICATION": ("test", "Test"),
}


class SeerrSource(Source):
    name = "seerr"

    def parse(self, payload: dict, ctx: Context) -> Event | None:
        kind = payload.get("notification_type")
        if not kind:
            raise PayloadError("missing notification_type")
        action, label = TYPES.get(kind, (kind.lower(), humanize(kind)))
        media = payload.get("media") or {}
        request = payload.get("request") or {}
        issue = payload.get("issue") or {}
        comment = payload.get("comment") or {}

        details = []
        if request.get("requestedBy_username"):
            details.append(f"Requested by {request['requestedBy_username']}")
        details += [join(e.get("name"), e.get("value"), sep=": ") for e in payload.get("extra") or [] if isinstance(e, dict)]
        if issue:
            details.append(join(humanize(issue.get("issue_type") or "") + " issue" if issue.get("issue_type") else "",
                                f"by {issue['reportedBy_username']}" if issue.get("reportedBy_username") else "", sep=" "))
            if action == "issue_created":
                details.append(payload.get("message") or "")
        if comment.get("comment_message"):
            details.append(join(comment.get("commentedBy_username"), comment["comment_message"], sep=": "))

        media_type = media.get("media_type") or ""
        issue_url = f"{ctx.seerr_url}/issues/{issue['issue_id']}" if ctx.seerr_url and issue.get("issue_id") else ""
        return Event(
            self.name, self.instance(payload, ctx),
            kind="generic" if action == "test" else "media",
            action=action, label=label,
            headline=payload.get("subject") or label,
            summary=payload.get("event") or label,
            details=details,
            image=payload.get("image") or "",
            url=issue_url,  # issues open in Seerr itself; requests use the app's tap
            emoji="🧪" if action == "test" else "",
            links=seerr_links(media_type, media.get("tmdbId"), ctx) if media_type in ("movie", "tv") else [],
        )
