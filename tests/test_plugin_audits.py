"""Integration tests for the three audit plugins."""
from __future__ import annotations

from kvault_mcp.kinds.audit import Audit
from kvault_mcp.testing import TempVault


def _audit(kernel, plugin_id: str) -> Audit:
    for a in kernel.get_all(Audit):
        if a.id == plugin_id:
            return a
    raise AssertionError(f"audit {plugin_id} not active")


def test_broken_wikilinks_flags_unresolved_targets() -> None:
    vault = TempVault()
    vault.__enter__()
    try:
        vault.write_file("AI/a.md", "links to [[Existing]] and [[Missing-One]]")
        vault.write_file("AI/Existing.md", "target")
        vault.set_config(
            {
                "plugins": {
                    "audit": {
                        "broken_wikilinks": {
                            "active": True,
                            "roots": ["AI"],
                            "extensions": [".md"],
                        }
                    }
                }
            }
        )
        kernel = vault.start_kernel()
        report = _audit(kernel, "audit.broken_wikilinks").run()
        messages = [f.message for f in report.findings]
        assert any("Missing-One" in m for m in messages)
        assert not any("Existing" in m for m in messages)
        assert report.summary["actionable_count"] >= 1
    finally:
        vault.__exit__(None, None, None)


def test_schemas_audit_catches_invalid_rows(tmp_path) -> None:
    vault = TempVault()
    vault.__enter__()
    try:
        # Write a manifest with one good row and one bad row.
        vault.write_file(
            "memory/semantic/caps.jsonl",
            '{"id": "plugin.one", "version": "1.0"}\n{"id": 42}\n',
        )
        # Write a small schema for that manifest.
        vault.write_file(
            "memory/semantic/schemas/caps.json",
            '{"$schema":"https://json-schema.org/draft/2020-12/schema",'
            '"type":"object",'
            '"properties":{"id":{"type":"string"},"version":{"type":"string"}},'
            '"required":["id","version"]}',
        )
        vault.set_config(
            {
                "plugins": {
                    "audit": {
                        "schemas": {
                            "active": True,
                            "targets": {
                                "memory/semantic/caps.jsonl":
                                    "memory/semantic/schemas/caps.json"
                            },
                        }
                    }
                }
            }
        )
        kernel = vault.start_kernel()
        report = _audit(kernel, "audit.schemas").run()
        # Row 2 fails both type (id should be string) and required (no version).
        assert report.summary["lines_validated"] == 2
        assert report.summary["actionable_count"] >= 1
        categories = {f.category for f in report.findings}
        assert "invalid_schema" in categories
    finally:
        vault.__exit__(None, None, None)


def test_lineage_dangling_reports_unknown_targets() -> None:
    vault = TempVault()
    vault.__enter__()
    try:
        vault.write_file(
            "memory/semantic/frameworks.jsonl",
            '{"id":"Frameworks/Memory-Harness.md","title":"Memory Harness",'
            '"path":"Frameworks/Memory-Harness.md"}\n',
        )
        vault.write_file(
            "memory/semantic/lineage.jsonl",
            '{"source":"AI/a.md","target":"Memory Harness"}\n'
            '{"source":"AI/a.md","target":"Nonexistent Framework"}\n',
        )
        vault.set_config(
            {
                "plugins": {
                    "audit": {"lineage_dangling": {"active": True}}
                }
            }
        )
        kernel = vault.start_kernel()
        report = _audit(kernel, "audit.lineage_dangling").run()
        targets = [f.location for f in report.findings]
        assert any("Nonexistent Framework" in loc for loc in targets)
        assert not any("Memory Harness" in loc for loc in targets)
    finally:
        vault.__exit__(None, None, None)
