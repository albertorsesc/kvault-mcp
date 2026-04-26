"""Vault-content parsing primitives shared across plugins.

Lives outside `plugins/` because it's infrastructure, not a plugin. Lives
outside `core/` because it's vault-shaped data (wikilinks, frontmatter,
markdown, JSONL), not kernel machinery.

Every export is a pure function or tiny stateless helper. No I/O beyond what
each module's docstring declares.
"""

from __future__ import annotations

from kvault_mcp.vault.frontmatter import parse_frontmatter
from kvault_mcp.vault.jsonl import atomic_write_jsonl, iter_jsonl
from kvault_mcp.vault.markdown import iter_markdown_files
from kvault_mcp.vault.wikilinks import WikiLink, extract_wikilinks

__all__ = [
    "WikiLink",
    "atomic_write_jsonl",
    "extract_wikilinks",
    "iter_jsonl",
    "iter_markdown_files",
    "parse_frontmatter",
]
