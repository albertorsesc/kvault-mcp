from __future__ import annotations

import sqlite3
from typing import Any

from kvault_mcp.kinds._types import RetrievalResult
from kvault_mcp.plugins.vector_store.sqlite_vec.serialization import (
    safe_identifier,
    serialize_float32,
)

_META_DDL = """
CREATE TABLE IF NOT EXISTS kvault_collections (
    collection_id TEXT PRIMARY KEY,
    dimensions    INTEGER NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    status        TEXT NOT NULL DEFAULT 'active'
);
"""


class VecCollections:
    """Per-collection vec0 operations on a sqlite-vec-loaded connection.

    Each collection is its own `vec_<id>` virtual table because vec0 fixes
    dimensions at creation; different embedding models need different tables.
    """

    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con
        self._con.executescript(_META_DDL)

    def create(self, collection_id: str, dimensions: int) -> None:
        safe = safe_identifier(collection_id)
        with self._con:
            self._con.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_{safe} USING vec0("
                f"  chunk_id TEXT PRIMARY KEY,"
                f"  embedding float[{int(dimensions)}]"
                f")"
            )
            self._con.execute(
                "INSERT OR REPLACE INTO kvault_collections"
                "(collection_id, dimensions, status) VALUES (?, ?, 'active')",
                (collection_id, dimensions),
            )

    def list_all(self) -> list[dict[str, Any]]:
        rows = self._con.execute(
            "SELECT collection_id, dimensions, created_at, status FROM kvault_collections"
        ).fetchall()
        return [
            {"collection_id": r[0], "dimensions": r[1], "created_at": r[2], "status": r[3]}
            for r in rows
        ]

    def add(self, collection_id: str, items: list[dict[str, Any]]) -> None:
        safe = safe_identifier(collection_id)
        with self._con:
            for item in items:
                self._con.execute(
                    f"INSERT OR REPLACE INTO vec_{safe}(chunk_id, embedding) VALUES (?, ?)",
                    (str(item["id"]), serialize_float32(list(item["embedding"]))),
                )

    def query(
        self, collection_id: str, vector: list[float], k: int = 5
    ) -> list[RetrievalResult]:
        safe = safe_identifier(collection_id)
        rows = self._con.execute(
            f"SELECT chunk_id, distance FROM vec_{safe} "
            f"WHERE embedding MATCH ? AND k = ? ORDER BY distance",
            (serialize_float32(vector), int(k)),
        ).fetchall()
        return [
            RetrievalResult(
                id=str(r[0]),
                score=-float(r[1]),  # distance smaller=better → negate for larger=better
                snippet="",
                metadata={"collection": collection_id, "distance": float(r[1])},
            )
            for r in rows
        ]
