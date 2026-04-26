from __future__ import annotations

from conftest import PLUGIN_SOURCES

from kvault_mcp.kinds.retriever import Retriever
from kvault_mcp.kinds.text_index import TextIndex
from kvault_mcp.testing import TempVault


def test_delegates_to_active_text_index() -> None:
    vault = TempVault()
    vault.__enter__()
    try:
        vault.write_file("notes/a.md", "agent harness memory")
        vault.install_plugin("text_index/fts5", PLUGIN_SOURCES["text_index/fts5"])
        vault.install_plugin("retriever/fts_only", PLUGIN_SOURCES["retriever/fts_only"])
        vault.set_config(
            {
                "plugins": {
                    "text_index": {
                        "fts5": {
                            "active": True,
                            "roots": ["notes"],
                            "extensions": [".md"],
                        }
                    },
                    "retriever": {"fts_only": {"active": True}},
                }
            }
        )
        kernel = vault.start_kernel()
        index = kernel.get_active(TextIndex)
        assert index is not None
        index.rebuild()

        retriever = kernel.get_active(Retriever)
        # Multiple retrievers may be registered (hybrid_rrf is too but not active);
        # fts_only is the only active one here.
        assert retriever is not None
        results = retriever.query("agent harness", k=5)
        assert results
        assert results[0].id.endswith("a.md")
    finally:
        vault.__exit__(None, None, None)


def test_no_text_index_returns_empty() -> None:
    vault = TempVault()
    vault.__enter__()
    try:
        vault.install_plugin("retriever/fts_only", PLUGIN_SOURCES["retriever/fts_only"])
        vault.set_config({"plugins": {"retriever": {"fts_only": {"active": True}}}})
        kernel = vault.start_kernel()
        retriever = kernel.get_active(Retriever)
        assert retriever is not None
        assert retriever.query("anything") == []
        health = retriever.health()  # type: ignore[union-attr]
        assert health["ok"] is False
    finally:
        vault.__exit__(None, None, None)
