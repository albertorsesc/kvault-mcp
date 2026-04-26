from __future__ import annotations

from conftest import PLUGIN_SOURCES

from kvault_mcp.kinds.text_index import TextIndex
from kvault_mcp.testing import TempVault


def _start_with_fts5(**cfg: object) -> tuple[TempVault, TextIndex]:
    defaults: dict[str, object] = {
        "active": True,
        "roots": ["notes"],
        "extensions": [".md"],
    }
    defaults.update(cfg)
    vault = TempVault()
    vault.__enter__()
    vault.install_plugin("text_index/fts5", PLUGIN_SOURCES["text_index/fts5"])
    vault.set_config({"plugins": {"text_index": {"fts5": defaults}}})
    kernel = vault.start_kernel()
    index = kernel.get_active(TextIndex)
    assert index is not None
    return vault, index


def test_rebuild_indexes_markdown_files() -> None:
    vault = TempVault()
    vault.__enter__()
    try:
        vault.write_file("notes/a.md", "agent harness memory systems")
        vault.write_file("notes/b.md", "prompt engineering patterns")
        vault.install_plugin("text_index/fts5", PLUGIN_SOURCES["text_index/fts5"])
        vault.set_config(
            {
                "plugins": {
                    "text_index": {"fts5": {"active": True, "roots": ["notes"], "extensions": [".md"]}}
                }
            }
        )
        kernel = vault.start_kernel()
        index = kernel.get_active(TextIndex)
        assert index is not None

        result = index.rebuild()
        assert result["indexed_count"] == 2

        hits = index.search("agent harness", k=5)
        assert hits
        assert hits[0].id.endswith("a.md")
    finally:
        vault.__exit__(None, None, None)


def test_special_chars_in_query_dont_raise() -> None:
    vault, index = _start_with_fts5()
    try:
        # FTS5 would treat `.md` as a syntax error; the sanitizer must tame it.
        assert index.search(".md NEAR(a b)", k=5) == []
    finally:
        vault.__exit__(None, None, None)


def test_index_and_delete_direct() -> None:
    vault, index = _start_with_fts5()
    try:
        index.index("manual_doc", "custom body text")
        assert any(h.id == "manual_doc" for h in index.search("custom", k=5))
        index.delete("manual_doc")
        assert not any(h.id == "manual_doc" for h in index.search("custom", k=5))
    finally:
        vault.__exit__(None, None, None)


def test_rebuild_emits_event() -> None:
    vault = TempVault()
    vault.__enter__()
    try:
        vault.write_file("notes/x.md", "content")
        vault.install_plugin("text_index/fts5", PLUGIN_SOURCES["text_index/fts5"])
        vault.set_config(
            {
                "plugins": {
                    "text_index": {"fts5": {"active": True, "roots": ["notes"], "extensions": [".md"]}}
                }
            }
        )
        kernel = vault.start_kernel()
        events: list[tuple[str, dict]] = []
        kernel.subscribe("vault.index.rebuilt", lambda e, p: events.append((e, p)))
        index = kernel.get_active(TextIndex)
        assert index is not None
        index.rebuild()
        assert len(events) == 1
        assert events[0][1]["indexed_count"] == 1
    finally:
        vault.__exit__(None, None, None)
