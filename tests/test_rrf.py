from __future__ import annotations

from kvault_mcp.plugins.retriever.hybrid_rrf.rrf import reciprocal_rank_fusion


def test_empty_inputs_produce_empty_output() -> None:
    assert reciprocal_rank_fusion([], k=60) == []
    assert reciprocal_rank_fusion([[]], k=60) == []
    assert reciprocal_rank_fusion([[], []], k=60) == []


def test_single_list_preserves_order() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"]], k=60)
    assert [doc for doc, _ in fused] == ["a", "b", "c"]


def test_cross_list_duplicates_sum() -> None:
    fts = ["a", "b", "c"]
    vec = ["c", "b", "d"]
    fused = dict(reciprocal_rank_fusion([fts, vec], k=60))
    # b: rank 2 in both → 2/(60+2) = 0.032258
    # c: rank 3 in FTS + rank 1 in VEC → 1/63 + 1/61 ≈ 0.032266
    # a: rank 1 in FTS only → 1/61 ≈ 0.016393
    # d: rank 3 in VEC only → 1/63 ≈ 0.015873
    # RRF rewards a rank-1 hit on either list; c edges b because its rank-1 counts more.
    assert fused["c"] > fused["a"]
    assert fused["b"] > fused["a"]
    assert fused["c"] > fused["d"]


def test_within_list_duplicates_count_once() -> None:
    # Only the first occurrence of "a" (rank 1) contributes.
    fused = dict(reciprocal_rank_fusion([["a", "a", "a"]], k=60))
    assert fused["a"] == 1.0 / (60 + 1)


def test_deterministic_tie_break_by_doc_id() -> None:
    fused = reciprocal_rank_fusion([["x"], ["y"]], k=60)
    # same score → sorted reverse by (score, id), so id tiebreaker descends: y, x
    assert [doc for doc, _ in fused] == ["y", "x"]
