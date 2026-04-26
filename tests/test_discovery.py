from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from conftest import TOY_PLUGIN

from kvault_mcp.core.discovery import discover_plugins


def _install(base: Path, kind: str, name: str, src: Path = TOY_PLUGIN) -> Path:
    dest = base / kind / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)
    return dest


def test_vault_local_discovery() -> None:
    vault = Path(tempfile.mkdtemp(prefix="kvault-disc-"))
    _install(vault / "kvault.plugins", "retriever", "toy")
    plugins = discover_plugins(vault, user_global_root=vault / "_nouser")
    ids = {p.id for p in plugins}
    assert "retriever.toy" in ids
    plugin = next(p for p in plugins if p.id == "retriever.toy")
    assert plugin.source == "vault_local"


def test_user_global_discovery() -> None:
    vault = Path(tempfile.mkdtemp(prefix="kvault-disc-"))
    user_global = Path(tempfile.mkdtemp(prefix="kvault-user-"))
    _install(user_global, "retriever", "toy")
    plugins = discover_plugins(vault, user_global_root=user_global)
    assert any(p.id == "retriever.toy" and p.source == "user_global" for p in plugins)


def test_vault_local_shadows_user_global() -> None:
    vault = Path(tempfile.mkdtemp(prefix="kvault-disc-"))
    user_global = Path(tempfile.mkdtemp(prefix="kvault-user-"))
    _install(user_global, "retriever", "toy")
    _install(vault / "kvault.plugins", "retriever", "toy")
    plugins = discover_plugins(vault, user_global_root=user_global)
    winners = [p for p in plugins if p.id == "retriever.toy"]
    assert len(winners) == 1
    assert winners[0].source == "vault_local"
    assert "user_global" in winners[0].shadows


def test_empty_vault_has_no_plugins() -> None:
    vault = Path(tempfile.mkdtemp(prefix="kvault-disc-"))
    plugins = discover_plugins(vault, user_global_root=vault / "_nouser")
    assert [p.id for p in plugins if p.source != "entry_point"] == []
