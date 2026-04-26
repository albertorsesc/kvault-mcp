from __future__ import annotations

import json
from collections.abc import Callable
from unittest.mock import patch

import pytest
from conftest import PLUGIN_SOURCES

from kvault_mcp.kinds.embedding import EmbeddingProvider
from kvault_mcp.testing import TempVault


def _fake_response(payload: dict) -> object:
    body = json.dumps(payload).encode("utf-8")

    class _Resp:
        def read(self) -> bytes:
            return body

        def __enter__(self):
            return self

        def __exit__(self, *a: object) -> None:
            pass

    return _Resp()


def _url_aware_side_effect(
    embed_batches: list[list[list[float]]] | None = None,
    tags_models: list[str] | None = None,
) -> Callable:
    """Build a urlopen side_effect that dispatches by URL path."""
    tags_payload = {"models": [{"name": n} for n in (tags_models or ["test-model:latest"])]}
    embed_iter = iter(embed_batches or [])

    def _side(req, *_args, **_kwargs):
        url = req if isinstance(req, str) else req.full_url
        if "/api/tags" in url:
            return _fake_response(tags_payload)
        if "/api/embed" in url:
            try:
                vectors = next(embed_iter)
            except StopIteration:
                raise AssertionError(f"unexpected embed call: {req.data!r}") from None
            return _fake_response({"embeddings": vectors})
        raise AssertionError(f"unmocked URL: {url}")

    return _side


def _ollama_vault(dimensions: int = 3, batch_size: int = 32) -> TempVault:
    """Build and enter a TempVault with ollama installed + active. Caller must __exit__."""
    vault = TempVault()
    vault.__enter__()
    vault.install_plugin("embedding/ollama", PLUGIN_SOURCES["embedding/ollama"])
    vault.set_config(
        {
            "plugins": {
                "embedding": {
                    "ollama": {
                        "active": True,
                        "dimensions": dimensions,
                        "batch_size": batch_size,
                        "model": "test-model",
                    }
                }
            }
        }
    )
    return vault


def _embed_call_count(mock_urlopen) -> int:
    return sum(
        1
        for c in mock_urlopen.call_args_list
        if "/api/embed" in (c.args[0] if isinstance(c.args[0], str) else c.args[0].full_url)
    )


def test_embed_happy_path_mocked() -> None:
    vault = _ollama_vault(dimensions=3)
    try:
        with patch(
            "kvault_mcp.plugins.embedding.ollama.client.request.urlopen"
        ) as mock_urlopen:
            mock_urlopen.side_effect = _url_aware_side_effect(
                embed_batches=[[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]]
            )
            kernel = vault.start_kernel()
            embedder = kernel.get_active(EmbeddingProvider)
            assert embedder is not None
            assert embedder.embed(["hello", "world"]) == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    finally:
        vault.__exit__(None, None, None)


def test_dimension_mismatch_raises() -> None:
    vault = _ollama_vault(dimensions=768)
    try:
        with patch(
            "kvault_mcp.plugins.embedding.ollama.client.request.urlopen"
        ) as mock_urlopen:
            mock_urlopen.side_effect = _url_aware_side_effect(
                embed_batches=[[[0.1, 0.2, 0.3, 0.4]]],
            )
            kernel = vault.start_kernel()
            embedder = kernel.get_active(EmbeddingProvider)
            assert embedder is not None
            with pytest.raises(RuntimeError, match="dimension mismatch"):
                embedder.embed(["hello"])
    finally:
        vault.__exit__(None, None, None)


def test_batching_issues_one_http_call_per_batch() -> None:
    vault = _ollama_vault(dimensions=2, batch_size=2)
    try:
        with patch(
            "kvault_mcp.plugins.embedding.ollama.client.request.urlopen"
        ) as mock_urlopen:
            batches = [
                [[0.0, 0.0], [0.1, 0.1]],
                [[0.2, 0.2], [0.3, 0.3]],
                [[0.4, 0.4]],
            ]
            mock_urlopen.side_effect = _url_aware_side_effect(embed_batches=batches)
            kernel = vault.start_kernel()
            embedder = kernel.get_active(EmbeddingProvider)
            assert embedder is not None
            result = embedder.embed(["a", "b", "c", "d", "e"])
            assert len(result) == 5
            assert _embed_call_count(mock_urlopen) == 3
    finally:
        vault.__exit__(None, None, None)


def test_shape_mismatch_raises() -> None:
    vault = _ollama_vault(dimensions=3)
    try:
        with patch(
            "kvault_mcp.plugins.embedding.ollama.client.request.urlopen"
        ) as mock_urlopen:
            mock_urlopen.side_effect = _url_aware_side_effect(
                embed_batches=[[[0.1, 0.2, 0.3]]],
            )
            kernel = vault.start_kernel()
            embedder = kernel.get_active(EmbeddingProvider)
            assert embedder is not None
            with pytest.raises(RuntimeError, match="unexpected response shape"):
                embedder.embed(["a", "b"])
    finally:
        vault.__exit__(None, None, None)


def test_health_reports_model_pulled() -> None:
    vault = _ollama_vault(dimensions=3)
    try:
        with patch(
            "kvault_mcp.plugins.embedding.ollama.client.request.urlopen"
        ) as mock_urlopen:
            mock_urlopen.side_effect = _url_aware_side_effect()
            kernel = vault.start_kernel()
            embedder = kernel.get_active(EmbeddingProvider)
            assert embedder is not None
            health = embedder.health()  # type: ignore[union-attr]
            assert health["ok"] is True
            assert health["model_pulled"] is True
    finally:
        vault.__exit__(None, None, None)


def test_embed_empty_list_makes_no_embed_call() -> None:
    vault = _ollama_vault(dimensions=3)
    try:
        with patch(
            "kvault_mcp.plugins.embedding.ollama.client.request.urlopen"
        ) as mock_urlopen:
            mock_urlopen.side_effect = _url_aware_side_effect()
            kernel = vault.start_kernel()
            embedder = kernel.get_active(EmbeddingProvider)
            assert embedder is not None
            assert embedder.embed([]) == []
            assert _embed_call_count(mock_urlopen) == 0
    finally:
        vault.__exit__(None, None, None)
