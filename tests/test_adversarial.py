"""Regression tests for adversarial findings.

Each failure here was a real bug at some point. Keep them green.
"""
from __future__ import annotations

import pytest

from kvault_mcp.core.eventbus import EventBus
from kvault_mcp.core.secrets import is_sensitive_key, redact_config
from kvault_mcp.core.state import PathEscape, StatePathResolver

# ── #1 Discovery must not crash on malformed plugin.toml ─────────────────


def test_discovery_survives_malformed_plugin_toml(tmp_path) -> None:
    from kvault_mcp.core.discovery import discover_plugins

    bad = tmp_path / "kvault.plugins" / "retriever" / "evil"
    bad.mkdir(parents=True)
    (bad / "plugin.toml").write_text("this is not = valid toml ][")
    # Even with a broken plugin, discovery must return (without the broken one).
    plugins = discover_plugins(tmp_path, user_global_root=tmp_path / "_nouser")
    ids = [p.id for p in plugins if p.source == "vault_local"]
    assert "retriever.evil" not in ids


# ── #2 state_path must refuse escapes ───────────────────────────────────


def test_state_path_rejects_parent_traversal(tmp_path) -> None:
    r = StatePathResolver(tmp_path, create=True)
    with pytest.raises(PathEscape):
        r.path("semantic", "../../../etc/passwd")


def test_state_path_rejects_absolute(tmp_path) -> None:
    r = StatePathResolver(tmp_path, create=True)
    with pytest.raises(PathEscape):
        r.path("semantic", "/etc/passwd")


def test_state_path_rejects_empty(tmp_path) -> None:
    r = StatePathResolver(tmp_path, create=True)
    with pytest.raises(PathEscape):
        r.path("semantic", "")


def test_state_path_allows_nested_subdir(tmp_path) -> None:
    r = StatePathResolver(tmp_path, create=True)
    p = r.path("semantic", "sub/dir/file.db")
    assert p.is_relative_to(tmp_path)
    assert p.name == "file.db"


# ── #7 EventBus handler identity surfaces in exception logs ─────────────


def test_eventbus_logs_handler_identity_on_failure() -> None:
    # kvault's logger has propagate=False, so caplog (root) won't see it.
    # Attach a dedicated handler that captures LogRecord objects directly.
    import logging

    captured: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    bus_logger = logging.getLogger("kvault.kernel.eventbus")
    handler = _Capture()
    bus_logger.addHandler(handler)
    try:
        bus = EventBus()

        def named_handler(event: str, payload: dict) -> None:
            raise RuntimeError("boom")

        bus.subscribe("x", named_handler)
        bus.publish("x", {})
    finally:
        bus_logger.removeHandler(handler)

    assert any(
        "named_handler" in str(getattr(r, "plugin_id", ""))
        for r in captured
    )


# ── #8 Redaction heuristic (suffix/exact match, not substring) ──────────


@pytest.mark.parametrize(
    "key",
    [
        "api_key",
        "API_KEY",
        "token",
        "secret",
        "password",
        "github_token",
        "stripe_api_key",
        "private_key",
        "bearer",
        "auth_token",
    ],
)
def test_redaction_flags_sensitive_keys(key: str) -> None:
    assert is_sensitive_key(key) is True


@pytest.mark.parametrize(
    "key",
    [
        "secret_path",  # false positive under the old substring heuristic
        "keystore_dir",
        "my_token_list_len",  # not a token itself
        "password_min_length",
        "endpoint",
        "normal_setting",
    ],
)
def test_redaction_skips_non_sensitive_keys(key: str) -> None:
    assert is_sensitive_key(key) is False


def test_redact_config_replaces_only_sensitive_string_values() -> None:
    cfg = {
        "api_key": "sk-xxx",
        "token": "ey.yyy",
        "endpoint": "http://local",
        "secret_path": "/etc/kv/secret",
        "dimensions": 768,  # non-string, not redacted regardless
    }
    out = redact_config(cfg)
    assert out["api_key"] == "***"
    assert out["token"] == "***"
    assert out["endpoint"] == "http://local"
    assert out["secret_path"] == "/etc/kv/secret"
    assert out["dimensions"] == 768


# ── Health is refreshed AFTER all plugins are wired ─────────────────────


def test_health_refreshed_after_all_plugins_registered() -> None:
    """retriever/fts_only depends on text_index/fts5 via the registry. Because
    'retriever.fts_only' alphabetizes before 'text_index.fts5', fts_only's
    __init__-time health() sees no TextIndex yet. After kernel.start() finishes
    wiring every plugin, the refreshed health must reflect the fully-wired
    system — ok=True.
    """
    from kvault_mcp.testing import TempVault

    vault = TempVault()
    vault.__enter__()
    try:
        vault.set_config(
            {
                "plugins": {
                    "text_index": {
                        "fts5": {"active": True, "roots": ["."], "extensions": [".md"]}
                    },
                    "retriever": {"fts_only": {"active": True}},
                }
            }
        )
        kernel = vault.start_kernel()
        fts_only = kernel.plugin_by_id("retriever.fts_only")
        assert fts_only is not None
        assert fts_only.health.get("ok") is True, fts_only.health
    finally:
        vault.__exit__(None, None, None)


# ── #10 kernel._set_plugin_config is the supported internal API ─────────


def test_set_plugin_config_is_available_on_kernel(tmp_path) -> None:
    from kvault_mcp.core.kernel import KernelCore

    (tmp_path / "kvault.config.toml").write_text("")
    k = KernelCore(tmp_path)
    k.start()
    k._set_plugin_config("retriever.demo", {"active": True, "k": 5})
    assert k.config("retriever.demo") == {"active": True, "k": 5}
