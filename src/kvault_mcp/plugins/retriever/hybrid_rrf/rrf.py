from __future__ import annotations

from collections.abc import Iterable, Sequence


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Iterable[str]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Fuse N ranked lists of doc IDs via RRF.

    Each inner iterable is best-to-worst ordered. Duplicates within a single
    list count only at their first rank. Cross-list duplicates sum — that is
    the point. Sort is descending by score, tie-broken by doc_id for
    determinism.
    """
    scores: dict[str, float] = {}
    for one_list in ranked_lists:
        seen: set[str] = set()
        for rank, doc_id in enumerate(one_list, start=1):
            if doc_id in seen:
                continue
            seen.add(doc_id)
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(
        scores.items(),
        key=lambda pair: (pair[1], pair[0]),
        reverse=True,
    )
