"""Parse the YAML-ish frontmatter block at the top of a markdown file."""

from __future__ import annotations

import re
from typing import Any

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_LIST_ITEM_RE = re.compile(r"^\s*-\s+(.*)$")
_KV_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")


def _coerce(raw: str) -> Any:
    s = raw.strip()
    if not s:
        return ""
    if s.lower() in {"true", "false"}:
        return s.lower() == "true"
    if s.lower() in {"null", "none", "~"}:
        return None
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return s


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Return the frontmatter block as a dict, or `{}` if none.

    Minimal YAML subset sufficient for kvault frontmatter: scalar values,
    single-line lists (`key: [a, b]`), and multi-line list blocks. No nested
    mappings, no block scalars. If the source uses anything richer, a full
    YAML parser should be added as a plugin-scoped dep — not to `core`.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    body = match.group(1)
    out: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[Any] | None = None
    for line in body.splitlines():
        if not line.strip():
            continue
        list_match = _LIST_ITEM_RE.match(line)
        if list_match and current_list is not None:
            current_list.append(_coerce(list_match.group(1)))
            continue
        kv = _KV_RE.match(line)
        if not kv:
            continue
        current_list = None
        key, raw_val = kv.group(1), kv.group(2).strip()
        if raw_val == "":
            current_list = []
            out[key] = current_list
            current_key = key
            continue
        if raw_val.startswith("[") and raw_val.endswith("]"):
            inner = raw_val[1:-1].strip()
            out[key] = (
                [_coerce(item) for item in inner.split(",")] if inner else []
            )
            continue
        out[key] = _coerce(raw_val)
        current_key = key
    _ = current_key  # retained for readability; parser is single-pass.
    return out
