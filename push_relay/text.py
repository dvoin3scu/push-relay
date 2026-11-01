"""Small text helpers shared by the adapters."""
from __future__ import annotations

import re


def join(*parts, sep: str = " · ") -> str:
    return sep.join(str(p) for p in parts if p not in (None, "", 0))


def size(num) -> str:
    try:
        b = int(num or 0)
    except (TypeError, ValueError):
        return ""
    if b <= 0:
        return ""
    if b >= 1024 ** 3:
        return f"{b / 1024 ** 3:.1f} GB"
    return f"{b / 1024 ** 2:.0f} MB"


def humanize(value: str) -> str:
    """'MEDIA_AUTO_APPROVED' / 'repair_failed' / 'ManualInteractionRequired' -> 'Media auto approved'."""
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value or "")
    value = value.replace("_", " ").replace("-", " ").strip().lower()
    return value[:1].upper() + value[1:]


def strip_markup(text: str, fmt: str = "text") -> str:
    if not text:
        return ""
    if fmt == "html":
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
    elif fmt == "markdown":
        text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
        text = re.sub(r"(\*\*|__|\*|_|~~|`)", "", text)
    return text.strip()


def year_of(value) -> str:
    m = re.search(r"(19|20)\d{2}", str(value or ""))
    return m.group(0) if m else ""
