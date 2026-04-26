"""Parse Obsidian-style `[[wikilinks]]` out of markdown text."""

from __future__ import annotations

import re
from dataclasses import dataclass

_WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")


@dataclass(frozen=True)
class WikiLink:
    target: str           # resolved target note title (before | or #)
    alias: str | None     # after |, if present
    section: str | None   # after #, if present
    raw: str              # full match including brackets


def extract_wikilinks(text: str) -> list[WikiLink]:
    """Return every `[[wikilink]]` in insertion order.

    Handles `[[Target]]`, `[[Target|Alias]]`, `[[Target#Section]]`, and
    `[[Target#Section|Alias]]`. Nested brackets are not matched (Obsidian
    doesn't allow them anyway).
    """
    out: list[WikiLink] = []
    for m in _WIKILINK_RE.finditer(text):
        inner = m.group(1).strip()
        alias: str | None = None
        section: str | None = None
        if "|" in inner:
            inner, alias = [p.strip() for p in inner.split("|", 1)]
        if "#" in inner:
            inner, section = [p.strip() for p in inner.split("#", 1)]
        if not inner:
            continue
        out.append(WikiLink(target=inner, alias=alias, section=section, raw=m.group(0)))
    return out
