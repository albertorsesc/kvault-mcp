from __future__ import annotations

from typing import Any

from conftest import PLUGIN_SOURCES

from kvault_mcp.kinds._types import RetrievalResult
from kvault_mcp.kinds.embedding import EmbeddingProvider
from kvault_mcp.kinds.retriever import Retriever
from kvault_mcp.kinds.text_index import TextIndex
from kvault_mcp.kinds.vector_store import VectorStore
from kvault_mcp.testing import TempVault


class _StubTextIndex:
    id = "text_index.stub"

    def __init__(self, hits: list[RetrievalResult]) -> None:
        self._hits = hits

    def index(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        pass

    def delete(self, doc_id: str) -> None:
        pass

    def search(self, query: str, k: int = 10) -> list[RetrievalResult]:
        return self._hits[:k]

    def rebuild(self) -> dict[str, Any]:
        return {}

    def health(self) -> dict[str, Any]:
        return {"ok": True}


class _StubEmbedder:
    id = "embedding.stub"
    dimensions = 3

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def health(self) -> dict[str, Any]:
        return {"ok": True}


class _StubVectorStore:
    id = "vector_store.stub"

    def __init__(self, hits: list[RetrievalResult]) -> None:
        self._hits = hits

    def collection_create(self, collection_id: str, dimensions: int) -> None:
        pass

    def collection_list(self) -> list[dict[str, Any]]:
        return []

    def add(self, collection_id: str, items: list[dict[str, Any]]) -> None:
        pass

    def query(
        self, collection_id: str, vector: list[float], k: int = 5
    ) -> list[RetrievalResult]:
        return self._hits[:k]

    def health(self) -> dict[str, Any]:
        return {"ok": True}


def _rr(doc_id: str, score: float = 1.0, snippet: str = "") -> RetrievalResult:
    return RetrievalResult(id=doc_id, score=score, snippet=snippet)


def _install_hybrid(
    vault: TempVault,
    text_hits: list[RetrievalResult],
    vec_hits: list[RetrievalResult],
    collection: str = "",
):
    vault.install_plugin("retriever/hybrid_rrf", PLUGIN_SOURCES["retriever/hybrid_rrf"])
    vault.set_config(
        {
            "plugins": {
                "retriever": {
                    "hybrid_rrf": {
                        "active": True,
                        "collection": collection,
                        "k_fts": 10,
                        "k_vec": 10,
                        "k_out": 5,
                        "rrf_k": 60,
                    }
                }
            }
        }
    )
    kernel = vault.start_kernel()
    # Register stubs directly against the kernel's registry. Documented as
    # test-only: normal usage goes through plugin discovery.
    kernel._registry.register(TextIndex, "text_index.stub", _StubTextIndex(text_hits), active=True)
    kernel._registry.register(
        EmbeddingProvider, "embedding.stub", _StubEmbedder(), active=True
    )
    kernel._registry.register(
        VectorStore, "vector_store.stub", _StubVectorStore(vec_hits), active=True
    )
    return kernel


def test_rrf_fuses_both_sources_and_respects_k_out() -> None:
    vault = TempVault()
    vault.__enter__()
    try:
        kernel = _install_hybrid(
            vault,
            text_hits=[_rr("a", snippet="A"), _rr("b"), _rr("c")],
            vec_hits=[_rr("c"), _rr("a"), _rr("d")],
            collection="notes_v1",
        )
        retriever = next(
            r for r in kernel.get_all(Retriever) if r.id == "retriever.hybrid_rrf"
        )
        results = retriever.query("anything", k=3)
        assert len(results) == 3
        ids = [r.id for r in results]
        # a appears at rank 1 in FTS and rank 2 in VEC → highest summed RRF
        # c appears at rank 3 in FTS and rank 1 in VEC
        assert ids[0] == "a"
        assert set(ids) == {"a", "c", "b"} or set(ids) == {"a", "c", "d"}
    finally:
        vault.__exit__(None, None, None)


def test_only_text_index_still_works() -> None:
    vault = TempVault()
    vault.__enter__()
    try:
        vault.install_plugin(
            "retriever/hybrid_rrf", PLUGIN_SOURCES["retriever/hybrid_rrf"]
        )
        vault.set_config(
            {"plugins": {"retriever": {"hybrid_rrf": {"active": True, "collection": ""}}}}
        )
        kernel = vault.start_kernel()
        kernel._registry.register(
            TextIndex,
            "text_index.stub",
            _StubTextIndex([_rr("only-a"), _rr("only-b")]),
            active=True,
        )
        retriever = next(
            r for r in kernel.get_all(Retriever) if r.id == "retriever.hybrid_rrf"
        )
        results = retriever.query("q", k=5)
        ids = [r.id for r in results]
        assert "only-a" in ids
        assert "only-b" in ids
        for r in results:
            assert r.metadata["from_fts"] is True
            assert r.metadata["from_vector"] is False
    finally:
        vault.__exit__(None, None, None)


def test_no_sources_health_fails() -> None:
    vault = TempVault()
    vault.__enter__()
    try:
        vault.install_plugin(
            "retriever/hybrid_rrf", PLUGIN_SOURCES["retriever/hybrid_rrf"]
        )
        vault.set_config(
            {"plugins": {"retriever": {"hybrid_rrf": {"active": True}}}}
        )
        kernel = vault.start_kernel()
        retriever = next(
            r for r in kernel.get_all(Retriever) if r.id == "retriever.hybrid_rrf"
        )
        health = retriever.health()  # type: ignore[union-attr]
        assert health["ok"] is False
    finally:
        vault.__exit__(None, None, None)
