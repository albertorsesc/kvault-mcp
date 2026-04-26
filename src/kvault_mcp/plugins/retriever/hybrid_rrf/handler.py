from __future__ import annotations

from typing import Any

from kvault_mcp.kinds._types import RetrievalResult
from kvault_mcp.kinds.embedding import EmbeddingProvider
from kvault_mcp.kinds.retriever import BaseRetriever
from kvault_mcp.kinds.text_index import TextIndex
from kvault_mcp.kinds.vector_store import VectorStore
from kvault_mcp.plugins.retriever.hybrid_rrf.merge import merge_results
from kvault_mcp.plugins.retriever.hybrid_rrf.rrf import reciprocal_rank_fusion


class HybridRrfRetriever(BaseRetriever):
    """Hybrid retriever composing TextIndex + VectorStore+EmbeddingProvider.

    Pulls dependencies from the kernel registry at query time — no plugin-to-
    plugin imports. Fuses with RRF; merges snippets/metadata via `merge_results`.
    """

    id = "retriever.hybrid_rrf"

    def __init__(self, kernel: Any) -> None:
        super().__init__(kernel)
        self._collection: str = str(self.cfg.get("collection", ""))
        self._k_fts: int = int(self.cfg["k_fts"])
        self._k_vec: int = int(self.cfg["k_vec"])
        self._k_out: int = int(self.cfg["k_out"])
        self._rrf_k: int = int(self.cfg["rrf_k"])

    def query(self, situation: str, k: int = 5) -> list[RetrievalResult]:
        fts_hits = self._fts_hits(situation)
        vec_hits = self._vector_hits(situation)
        fused = reciprocal_rank_fusion(
            [[h.id for h in fts_hits], [h.id for h in vec_hits]],
            k=self._rrf_k,
        )
        return merge_results(fused, fts_hits, vec_hits, limit=min(int(k), self._k_out))

    def health(self) -> dict[str, Any]:
        sources = {
            "text_index": self.kernel.get_active(TextIndex) is not None,
            "embedding": self.kernel.get_active(EmbeddingProvider) is not None,
            "vector_store": self.kernel.get_active(VectorStore) is not None,
            "collection": bool(self._collection),
        }
        usable_fts = sources["text_index"]
        usable_vec = sources["embedding"] and sources["vector_store"] and sources["collection"]
        if not (usable_fts or usable_vec):
            return {"ok": False, "reason": "no usable retrieval source", "sources": sources}
        return {"ok": True, "sources": sources}

    def _fts_hits(self, situation: str) -> list[RetrievalResult]:
        text_index = self.kernel.get_active(TextIndex)
        if text_index is None:
            return []
        return text_index.search(situation, k=self._k_fts)

    def _vector_hits(self, situation: str) -> list[RetrievalResult]:
        if not self._collection:
            return []
        embedder = self.kernel.get_active(EmbeddingProvider)
        vectors = self.kernel.get_active(VectorStore)
        if embedder is None or vectors is None:
            return []
        try:
            vec = embedder.embed([situation])[0]
            return vectors.query(self._collection, vec, k=self._k_vec)
        except Exception:
            self.log.exception(
                "vector query failed; continuing without vector hits",
                extra={"event": "hybrid.vector_error"},
            )
            return []
