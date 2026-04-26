from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from kvault_mcp.core.state import StatePathResolver


def test_all_categories_resolve_and_create() -> None:
    root = Path(tempfile.mkdtemp(prefix="kvault-state-"))
    resolver = StatePathResolver(root, create=True)
    for category in StatePathResolver.categories():
        path = resolver.path(category)
        assert path.exists() and path.is_dir()
        assert path.is_relative_to(root)


def test_path_with_name_appended() -> None:
    root = Path(tempfile.mkdtemp(prefix="kvault-state-"))
    resolver = StatePathResolver(root, create=True)
    path = resolver.path("semantic", "vault-capabilities.jsonl")
    assert path == root / "memory" / "semantic" / "vault-capabilities.jsonl"


def test_unknown_category_raises() -> None:
    root = Path(tempfile.mkdtemp(prefix="kvault-state-"))
    resolver = StatePathResolver(root, create=True)
    with pytest.raises(KeyError):
        resolver.path("unknown")


def test_no_create_flag() -> None:
    root = Path(tempfile.mkdtemp(prefix="kvault-state-"))
    resolver = StatePathResolver(root, create=False)
    path = resolver.path("episodic")
    assert not path.exists()
