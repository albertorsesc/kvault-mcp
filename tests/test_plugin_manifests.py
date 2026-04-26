"""Integration tests for the three manifest-builder plugins."""
from __future__ import annotations

import json

from kvault_mcp.kinds.manifest_builder import ManifestBuilder
from kvault_mcp.testing import TempVault


def _start_with(cfg: dict) -> TempVault:
    vault = TempVault()
    vault.__enter__()
    vault.set_config(cfg)
    return vault


def test_capabilities_manifest_lists_every_plugin() -> None:
    vault = _start_with(
        {
            "plugins": {
                "manifest_builder": {
                    "capabilities": {
                        "active": True,
                        "output": "memory/semantic/caps.jsonl",
                    }
                }
            }
        }
    )
    try:
        kernel = vault.start_kernel()
        builder = next(
            b for b in kernel.get_all(ManifestBuilder) if b.id.endswith(".capabilities")
        )
        result = builder.build()
        assert result["count"] >= 1
        rows = [
            json.loads(line)
            for line in (vault.root / "memory/semantic/caps.jsonl").read_text().splitlines()
            if line.strip()
        ]
        ids = {r["id"] for r in rows}
        assert {
            "embedding.ollama",
            "text_index.fts5",
            "retriever.fts_only",
        } <= ids
    finally:
        vault.__exit__(None, None, None)


def test_frameworks_manifest_extracts_title_and_frontmatter() -> None:
    vault = _start_with({})
    try:
        vault.write_file(
            "Frameworks/Memory-Harness.md",
            "---\ntitle: Memory Harness\ndomain: AI\n---\n\n# Memory Harness\n\nbody",
        )
        vault.write_file(
            "Frameworks/Plain.md",
            "# Plain Note\n\nno frontmatter here",
        )
        vault.set_config(
            {
                "plugins": {
                    "manifest_builder": {
                        "frameworks": {
                            "active": True,
                            "roots": ["Frameworks"],
                            "output": "memory/semantic/fw.jsonl",
                        }
                    }
                }
            }
        )
        kernel = vault.start_kernel()
        builder = next(
            b for b in kernel.get_all(ManifestBuilder) if b.id.endswith(".frameworks")
        )
        result = builder.build()
        assert result["count"] == 2
        rows = [
            json.loads(line)
            for line in (vault.root / "memory/semantic/fw.jsonl").read_text().splitlines()
            if line.strip()
        ]
        titles = {r["title"] for r in rows}
        assert titles == {"Memory Harness", "Plain Note"}
        harness = next(r for r in rows if r["title"] == "Memory Harness")
        assert harness["frontmatter"]["domain"] == "AI"
    finally:
        vault.__exit__(None, None, None)


def test_lineage_manifest_captures_wikilink_edges() -> None:
    vault = _start_with({})
    try:
        vault.write_file(
            "AI/note-a.md",
            "Uses [[Memory Harness]] and [[Loss Aversion|LA]].",
        )
        vault.write_file(
            "AI/note-b.md",
            "Unrelated note with no links.",
        )
        vault.set_config(
            {
                "plugins": {
                    "manifest_builder": {
                        "lineage": {
                            "active": True,
                            "roots": ["AI"],
                            "output": "memory/semantic/lin.jsonl",
                        }
                    }
                }
            }
        )
        kernel = vault.start_kernel()
        builder = next(
            b for b in kernel.get_all(ManifestBuilder) if b.id.endswith(".lineage")
        )
        result = builder.build()
        assert result["count"] == 2  # two links from note-a.md
        rows = [
            json.loads(line)
            for line in (vault.root / "memory/semantic/lin.jsonl").read_text().splitlines()
            if line.strip()
        ]
        pairs = {(r["source"], r["target"]) for r in rows}
        assert ("AI/note-a.md", "Memory Harness") in pairs
        assert ("AI/note-a.md", "Loss Aversion") in pairs
    finally:
        vault.__exit__(None, None, None)
