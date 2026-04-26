"""Integration tests for the rules lifecycle (store + injector)."""
from __future__ import annotations

from kvault_mcp.kinds.rule_injector import RuleInjector
from kvault_mcp.kinds.rule_store import RuleStore
from kvault_mcp.testing import TempVault


def _start() -> TempVault:
    vault = TempVault()
    vault.__enter__()
    vault.set_config(
        {
            "plugins": {
                "rule_store": {"markdown": {"active": True}},
                "rule_injector": {
                    "markdown_markers": {
                        "active": True,
                        "target": "CLAUDE.md",
                        "create_if_missing": True,
                    }
                },
            }
        }
    )
    return vault


def test_propose_approve_retire_roundtrip() -> None:
    vault = _start()
    try:
        kernel = vault.start_kernel()
        store = kernel.get_active(RuleStore)
        assert store is not None

        r = store.propose(
            "no-mock-db",
            title="Integration tests must use real databases",
            body="Mocked databases hide migration bugs.",
            rule_type="feedback",
        )
        assert r.status == "proposed"
        assert (vault.root / "memory/rules/proposed/no-mock-db.md").exists()

        active = store.approve("no-mock-db")
        assert active.status == "active"
        assert not (vault.root / "memory/rules/proposed/no-mock-db.md").exists()
        assert (vault.root / "memory/rules/active/no-mock-db.md").exists()

        retired = store.retire("no-mock-db", reason="no longer applies")
        assert retired.status == "retired"
        assert retired.frontmatter.get("retired_reason") == "no longer applies"
        assert (vault.root / "memory/rules/retired/no-mock-db.md").exists()

        listed = store.list(status="retired")
        assert [x.id for x in listed] == ["no-mock-db"]
    finally:
        vault.__exit__(None, None, None)


def test_injector_writes_active_rules_between_markers() -> None:
    vault = _start()
    try:
        kernel = vault.start_kernel()
        store = kernel.get_active(RuleStore)
        injector = kernel.get_active(RuleInjector)
        assert store is not None and injector is not None

        store.propose(
            "terse-responses",
            title="Default to terse responses",
            body="Cut preamble; 1-2 sentence end-of-turn max.",
            rule_type="feedback",
        )
        store.approve("terse-responses")

        result = injector.inject()
        assert result["ok"] is True
        body = (vault.root / "CLAUDE.md").read_text()
        assert "<!-- kvault:rules:start -->" in body
        assert "<!-- kvault:rules:end -->" in body
        assert "Default to terse responses" in body
        assert "[terse-responses]" in body
    finally:
        vault.__exit__(None, None, None)


def test_injector_idempotent_and_replaces_block_in_place() -> None:
    vault = _start()
    try:
        kernel = vault.start_kernel()
        store = kernel.get_active(RuleStore)
        injector = kernel.get_active(RuleInjector)
        assert store is not None and injector is not None

        # Seed a CLAUDE.md with existing content outside the markers.
        (vault.root / "CLAUDE.md").write_text(
            "# Instructions\n\nexisting content above the block.\n\n"
        )

        store.propose("r1", title="Rule One", body="first rule body", rule_type="user")
        store.approve("r1")
        injector.inject()

        store.propose("r2", title="Rule Two", body="second rule body", rule_type="user")
        store.approve("r2")
        injector.inject()

        body = (vault.root / "CLAUDE.md").read_text()
        # The existing content survived.
        assert "existing content above the block." in body
        # Both rules appear exactly once.
        assert body.count("Rule One") == 1
        assert body.count("Rule Two") == 1
        # Only one marker block exists.
        assert body.count("<!-- kvault:rules:start -->") == 1
    finally:
        vault.__exit__(None, None, None)


def test_injector_auto_refreshes_on_rule_activation() -> None:
    vault = _start()
    try:
        kernel = vault.start_kernel()
        store = kernel.get_active(RuleStore)
        injector = kernel.get_active(RuleInjector)
        assert store is not None and injector is not None

        # Approve triggers vault.rule.activated — injector consumes_events
        # subscribes and auto-renders. No explicit inject() call here.
        store.propose("auto", title="Auto injected", body="body", rule_type="user")
        store.approve("auto")

        body = (vault.root / "CLAUDE.md").read_text()
        assert "Auto injected" in body
        assert "[auto]" in body
    finally:
        vault.__exit__(None, None, None)
