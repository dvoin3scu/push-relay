"""Logic-less JSON templates.

A template is a JSON file per backend and kind (templates/<backend>/<kind>.json).
Every string value may use:

    {{name}}                   value from the view
    {{#name}}...{{/name}}      block shown only when name is non-empty
    {{^name}}...{{/name}}      block shown only when name is empty

A value that is exactly "{{name}}" is replaced by the raw view value (list, number, ...).
Fields that end up empty are dropped, so the backend never receives blank keys.

Lookup order (first file found wins):
    <config>/templates/<backend>/<source>.<kind>.json
    <config>/templates/<backend>/<kind>.json
    defaults/templates/<backend>/<source>.<kind>.json
    defaults/templates/<backend>/<kind>.json
    ... then the same with kind "generic".
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger("push-relay")

DEFAULTS_DIR = Path(__file__).parent / "defaults" / "templates"

_SECTION = re.compile(r"\{\{([#^])(\w+)\}\}(.*?)\{\{/\2\}\}", re.S)
_VAR = re.compile(r"\{\{(\w+)\}\}")
_RAW = re.compile(r"^\{\{(\w+)\}\}$")


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def render_string(template: str, view: dict) -> str:
    previous = None
    while previous != template:  # resolve nested sections from the inside out
        previous = template
        template = _SECTION.sub(
            lambda m: m.group(3) if bool(view.get(m.group(2))) == (m.group(1) == "#") else "",
            template,
        )
    return _VAR.sub(lambda m: _text(view.get(m.group(1))), template).strip()


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def render(template: Any, view: dict) -> Any:
    if isinstance(template, str):
        raw = _RAW.match(template)
        if raw:
            return view.get(raw.group(1))
        return render_string(template, view)
    if isinstance(template, dict):
        rendered = {key: render(value, view) for key, value in template.items()}
        return {key: value for key, value in rendered.items() if not _empty(value)}
    if isinstance(template, list):
        return [item for item in (render(v, view) for v in template) if not _empty(item)]
    return template


class TemplateStore:
    def __init__(self, config_dir: Path | None = None):
        self._dirs = [d for d in ((config_dir / "templates") if config_dir else None, DEFAULTS_DIR) if d]
        self._cache: dict[Path, Any] = {}

    def find(self, backend: str, source: str, kind: str) -> Any:
        for k in dict.fromkeys((kind, "generic")):
            for base in self._dirs:
                for name in (f"{source}.{k}.json", f"{k}.json"):
                    path = base / backend / name
                    if path.is_file():
                        return self._read(path)
        raise LookupError(f"no {backend} template for {source}/{kind}")

    def _read(self, path: Path) -> Any:
        mtime = path.stat().st_mtime
        cached = self._cache.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
        data = json.loads(path.read_text())
        self._cache[path] = (mtime, data)
        return data

    def render(self, backend: str, source: str, kind: str, view: dict) -> dict:
        return render(self.find(backend, source, kind), view)
