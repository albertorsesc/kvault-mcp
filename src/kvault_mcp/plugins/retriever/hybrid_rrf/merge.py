from __future__ import annotations

from typing import Any

from kvault_mcp.kinds._types import RetrievalResult


def merge_results(
    fused: list[tuple[str, float]],
    fts_hits: list[RetrievalResult],
    vec_hits: list[RetrievalResult],
    limit: int,
) -> list[RetrievalResult]:
    """Build output RetrievalResult list from RRF-fused doc IDs + source hits.

    Attaches snippet + metadata from the first source list that contained each
    doc. FTS preferred for snippet (it has a BM25-highlighted preview); vector
    metadata is prefixed `vector_*`.
    """
    fts_by_id = {h.id: h for h in fts_hits}
    vec_by_id = {h.id: h for h in vec_hits}

    out: list[RetrievalResult] = []
    for doc_id, score in fused[:limit]:
        fts_src = fts_by_id.get(doc_id)
        vec_src = vec_by_id.get(doc_id)
        snippet = (fts_src.snippet if fts_src else (vec_src.snippet if vec_src else ""))
        metadata: dict[str, Any] = {
            "rrf_score": score,
            "from_fts": fts_src is not None,
            "from_vector": vec_src is not None,
        }
        if fts_src is not None:
            metadata.update(fts_src.metadata)
        if vec_src is not None:
            for key, val in vec_src.metadata.items():
                metadata.setdefault(f"vector_{key}", val)
        out.append(
            RetrievalResult(id=doc_id, score=float(score), snippet=snippet, metadata=metadata)
        )
    return out
