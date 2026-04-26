from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from kvault_mcp.kinds._types import RetrievalResult
from kvault_mcp.plugins.text_index.fts5.hashing import stable_rowid
from kvault_mcp.plugins.text_index.fts5.query import sanitize_fts_query

_DEFAULT_TOKENIZER = "porter unicode61 remove_diacritics 2"
_SINGLE_QUOTE = re.compile(r"'")


class Fts5Store:
    """Owns the SQLite connection, FTS5 schema, and low-level CRUD.

    Does NOT walk the filesystem. File-scanning lives in `MarkdownIndexer`.
    """

    def __init__(self, db_path: Path, tokenizer: str | None = None) -> None:
        self._db_path = db_path
        self._tokenizer = self._safe_tokenizer(tokenizer)
        # check_same_thread=False: MCP dispatch may call search() from a
        # different thread than the one that opened the connection. SQLite's
        # own thread safety handles concurrent reads; writes are naturally
        # serialized by the outer `with self._con:` transaction context.
        self._con = sqlite3.connect(db_path, check_same_thread=False)
        self._ensure_schema()

    @staticmethod
    def _safe_tokenizer(raw: str | None) -> str:
        candidate = raw if raw else _DEFAULT_TOKENIZER
        if _SINGLE_QUOTE.search(candidate):
            return _DEFAULT_TOKENIZER
        return candidate

    def _ensure_schema(self) -> None:
        # Standard (non-contentless) FTS5: body + UNINDEXED source_path are
        # stored inline and retrievable. Contentless FTS5 drops UNINDEXED
        # column values too, which would make snippet citations unrecoverable.
        # The ~2x disk cost is acceptable for vault-scale corpora (< 1M docs).
        with self._con:
            self._con.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
                    source_path UNINDEXED,
                    body,
                    tokenize = '{self._tokenizer}'
                )
                """
            )

    def upsert(self, doc_id: str, text: str) -> None:
        rowid = stable_rowid(doc_id)
        with self._con:
            self._con.execute("DELETE FROM fts WHERE rowid = ?", (rowid,))
            self._con.execute(
                "INSERT INTO fts(rowid, source_path, body) VALUES (?, ?, ?)",
                (rowid, doc_id, text),
            )

    def delete(self, doc_id: str) -> None:
        with self._con:
            self._con.execute("DELETE FROM fts WHERE rowid = ?", (stable_rowid(doc_id),))

    def truncate(self) -> None:
        with self._con:
            self._con.execute("DELETE FROM fts")

    def optimize(self) -> None:
        with self._con:
            self._con.execute("INSERT INTO fts(fts) VALUES ('optimize')")

    def search(self, query: str, k: int = 10) -> list[RetrievalResult]:
        match = sanitize_fts_query(query)
        rows = self._con.execute(
            """
            SELECT source_path, bm25(fts) AS score,
                   snippet(fts, 1, '<b>', '</b>', '…', 16) AS preview
            FROM fts WHERE fts MATCH ?
            ORDER BY bm25(fts) LIMIT ?
            """,
            (match, int(k)),
        ).fetchall()
        return [
            RetrievalResult(
                id=str(r[0]),
                score=-float(r[1]),  # bm25 is smaller-is-better → negate
                snippet=str(r[2]),
                metadata={"bm25": float(r[1])},
            )
            for r in rows
        ]

    def count(self) -> int:
        return int(self._con.execute("SELECT count(*) FROM fts").fetchone()[0])

    @property
    def db_path(self) -> Path:
        return self._db_path
