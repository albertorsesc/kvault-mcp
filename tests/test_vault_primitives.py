"""Unit tests for the shared vault/ parsing primitives."""
from __future__ import annotations

from kvault_mcp.vault import (
    atomic_write_jsonl,
    extract_wikilinks,
    iter_jsonl,
    iter_markdown_files,
    parse_frontmatter,
)


def test_wikilinks_basic() -> None:
    text = "See [[Foo]] and [[Bar|alias]] and [[Baz#section]] and [[Q#sec|a]]"
    links = extract_wikilinks(text)
    targets = [link.target for link in links]
    assert targets == ["Foo", "Bar", "Baz", "Q"]
    assert links[1].alias == "alias"
    assert links[2].section == "section"
    assert links[3].section == "sec"
    assert links[3].alias == "a"


def test_wikilinks_nested_brackets_ignored() -> None:
    text = "[[outer [[inner]] close]]"
    links = extract_wikilinks(text)
    assert [link.target for link in links] == ["inner"]


def test_wikilinks_empty_skipped() -> None:
    assert extract_wikilinks("[[]] and [[   ]]") == []


def test_frontmatter_scalars_and_lists() -> None:
    text = """---
title: Memory Harness
created: 2026-04-24
active: true
score: 9.5
tags:
  - memory
  - harness
frameworks: [A, B, C]
---

# body
"""
    fm = parse_frontmatter(text)
    assert fm["title"] == "Memory Harness"
    assert fm["active"] is True
    assert fm["score"] == 9.5
    assert fm["tags"] == ["memory", "harness"]
    assert fm["frameworks"] == ["A", "B", "C"]


def test_frontmatter_no_block() -> None:
    assert parse_frontmatter("# just a heading") == {}


def test_jsonl_atomic_roundtrip(tmp_path) -> None:
    target = tmp_path / "out.jsonl"
    rows = [{"a": 1}, {"b": 2, "c": [3, 4]}]
    count = atomic_write_jsonl(target, rows)
    assert count == 2
    assert list(iter_jsonl(target)) == rows


def test_jsonl_no_partial_writes_on_failure(tmp_path) -> None:
    target = tmp_path / "out.jsonl"
    target.write_text('{"prior": true}\n')

    class BoomIter:
        def __iter__(self):
            yield {"fine": 1}
            raise RuntimeError("boom")

    try:
        atomic_write_jsonl(target, BoomIter())
    except RuntimeError:
        pass
    # Previous content still intact — no partial overwrite.
    assert target.read_text() == '{"prior": true}\n'


def test_iter_markdown_skips_hidden_dirs(tmp_path) -> None:
    (tmp_path / "notes" / ".obsidian").mkdir(parents=True)
    (tmp_path / "notes" / ".obsidian" / "config.md").write_text("hidden")
    (tmp_path / "notes" / "a.md").write_text("visible")
    (tmp_path / "notes" / "b.txt").write_text("wrong ext")
    found = sorted(p.name for p in iter_markdown_files(tmp_path, ["notes"], (".md",)))
    assert found == ["a.md"]
