from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from kvault_mcp.kinds._types import RetrievalResult
from kvault_mcp.kinds.text_index import BaseTextIndex
from kvault_mcp.plugins.text_index.fts5.indexer import MarkdownIndexer
from kvault_mcp.plugins.text_index.fts5.store import Fts5Store


class Fts5TextIndex(BaseTextIndex):
    """FTS5-backed text index. Plugin = thin composer over Fts5Store + MarkdownIndexer."""

    id = "text_index.fts5"

    def __init__(self, kernel: Any) -> None:
        super().__init__(kernel)
        db_rel = Path(self.cfg["db_path"])
        db_path = db_rel if db_rel.is_absolute() else self.vault_root / db_rel
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._store = Fts5Store(db_path, tokenizer=self.cfg.get("tokenizer"))
        self._indexer = MarkdownIndexer(
            store=self._store,
            vault_root=self.vault_root,
            roots=self.cfg["roots"],
            extensions=self.cfg["extensions"],
        )

    def index(
        self, doc_id: str, text: str, metadata: dict[str, Any] | None = None
    ) -> None:
        self._store.upsert(doc_id, text)

    def delete(self, doc_id: str) -> None:
        self._store.delete(doc_id)

    def search(self, query: str, k: int = 10) -> list[RetrievalResult]:
        return self._store.search(query, k=k)

    def rebuild(self) -> dict[str, Any]:
        indexed = self._indexer.rebuild()
        self.kernel.publish(
            "vault.index.rebuilt",
            {"plugin_id": self.id, "indexed_count": indexed},
        )
        return {"indexed_count": indexed, "db_path": str(self._store.db_path)}

    def health(self) -> dict[str, Any]:
        try:
            doc_count = self._store.count()
        except sqlite3.OperationalError as e:
            return {"ok": False, "reason": str(e)}
        return {"ok": True, "db_path": str(self._store.db_path), "doc_count": doc_count}
