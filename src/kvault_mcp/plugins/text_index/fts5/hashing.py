from __future__ import annotations

import hashlib


def stable_rowid(doc_id: str) -> int:
    """Deterministic 63-bit positive int derived from an arbitrary doc_id string."""
    digest = hashlib.blake2b(doc_id.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=False) & ((1 << 63) - 1)
