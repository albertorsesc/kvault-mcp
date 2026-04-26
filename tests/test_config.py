from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from kvault_mcp.core.config import ConfigResolver


def _vault_with_toml(body: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix="kvault-cfg-"))
    (d / "kvault.config.toml").write_text(body)
    return d


def test_defaults_from_schema() -> None:
    vault = _vault_with_toml("")
    resolver = ConfigResolver(vault, env={})
    schema = {
        "type": "object",
        "properties": {
            "active": {"type": "boolean", "default": False},
            "endpoint": {"type": "string", "default": "http://localhost:11434"},
        },
    }
    resolved = resolver.resolve_plugin("embedding.ollama", schema)
    assert resolved == {"active": False, "endpoint": "http://localhost:11434"}


def test_toml_overrides_defaults() -> None:
    vault = _vault_with_toml(
        """
        [plugins.embedding.ollama]
        active = true
        endpoint = "http://remote:11434"
        """
    )
    resolver = ConfigResolver(vault, env={})
    schema = {
        "type": "object",
        "properties": {
            "active": {"type": "boolean", "default": False},
            "endpoint": {"type": "string", "default": "http://localhost:11434"},
        },
    }
    resolved = resolver.resolve_plugin("embedding.ollama", schema)
    assert resolved["active"] is True
    assert resolved["endpoint"] == "http://remote:11434"


def test_env_overrides_toml() -> None:
    vault = _vault_with_toml(
        """
        [plugins.embedding.ollama]
        endpoint = "http://remote:11434"
        """
    )
    env = {"KVAULT_EMBEDDING_OLLAMA_ENDPOINT": "http://override:11434"}
    resolver = ConfigResolver(vault, env=env)
    schema = {
        "type": "object",
        "properties": {"endpoint": {"type": "string"}},
    }
    resolved = resolver.resolve_plugin("embedding.ollama", schema)
    assert resolved["endpoint"] == "http://override:11434"


def test_env_coerces_bool_and_int() -> None:
    vault = _vault_with_toml("")
    env = {
        "KVAULT_RETRIEVER_HYBRID_K_FTS": "40",
        "KVAULT_RETRIEVER_HYBRID_ACTIVE": "true",
    }
    resolver = ConfigResolver(vault, env=env)
    resolved = resolver.resolve_plugin("retriever.hybrid", schema=None)
    assert resolved["k_fts"] == 40
    assert resolved["active"] is True


def test_invalid_plugin_id_shape() -> None:
    vault = _vault_with_toml("")
    resolver = ConfigResolver(vault, env={})
    with pytest.raises(ValueError):
        resolver.resolve_plugin("just-a-name", schema=None)


def test_schema_validation_failure() -> None:
    vault = _vault_with_toml(
        """
        [plugins.embedding.ollama]
        endpoint = 42
        """
    )
    resolver = ConfigResolver(vault, env={})
    schema = {"type": "object", "properties": {"endpoint": {"type": "string"}}}
    with pytest.raises(ValueError, match="endpoint"):
        resolver.resolve_plugin("embedding.ollama", schema)
