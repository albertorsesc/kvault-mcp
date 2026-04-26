from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from kvault_mcp.kinds._types import RetrievalResult
from kvault_mcp.kinds.vector_store import BaseVectorStore
from kvault_mcp.plugins.vector_store.sqlite_vec.collections import VecCollections
from kvault_mcp.plugins.vector_store.sqlite_vec.connection import open_connection


class SqliteVecStore(BaseVectorStore):
    """sqlite-vec backed vector store. Plugin = thin composer over VecCollections."""

    id = "vector_store.sqlite_vec"

    def __init__(self, kernel: Any) -> None:
        super().__init__(kernel)
        db_rel = Path(self.cfg["path"])
        self._db_path = db_rel if db_rel.is_absolute() else self.vault_root / db_rel
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._load_error: str | None = None
        self._con: sqlite3.Connection | None = None
        self._collections: VecCollections | None = None
        try:
            self._con = open_connection(self._db_path)
            self._collections = VecCollections(self._con)
        except Exception as e:
            self._load_error = str(e)
            self.log.warning(
                "sqlite-vec unavailable",
                extra={"event": "vector_store.unavailable"},
            )

    def collection_create(self, collection_id: str, dimensions: int) -> None:
        self._require().create(collection_id, dimensions)

    def collection_list(self) -> list[dict[str, Any]]:
        if self._collections is None:
            return []
        return self._collections.list_all()

    def add(self, collection_id: str, items: list[dict[str, Any]]) -> None:
        self._require().add(collection_id, items)

    def query(
        self, collection_id: str, vector: list[float], k: int = 5
    ) -> list[RetrievalResult]:
        return self._require().query(collection_id, vector, k=k)

    def health(self) -> dict[str, Any]:
        if self._load_error is not None or self._con is None:
            return {"ok": False, "reason": self._load_error or "not initialized"}
        try:
            version = self._con.execute("SELECT vec_version()").fetchone()[0]
        except sqlite3.OperationalError as e:
            return {"ok": False, "reason": f"vec_version() failed: {e}"}
        return {
            "ok": True,
            "db_path": str(self._db_path),
            "sqlite_vec_version": version,
            "collection_count": len(self.collection_list()),
        }

    def _require(self) -> VecCollections:
        if self._collections is None:
            raise RuntimeError(f"vector store unavailable: {self._load_error}")
        return self._collections
