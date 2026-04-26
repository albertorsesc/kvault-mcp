from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from kvault_mcp.plugins.text_index.fts5.store import Fts5Store


class MarkdownIndexer:
    """Walks configured roots, reads files, upserts into an Fts5Store.

    Stateless walker — no side effects beyond the store it was handed.
    """

    def __init__(
        self,
        store: Fts5Store,
        vault_root: Path,
        roots: Iterable[str],
        extensions: Iterable[str],
    ) -> None:
        self._store = store
        self._vault_root = vault_root
        self._roots = [self._resolve(r) for r in roots]
        self._extensions = tuple(str(e).lower() for e in extensions)

    def rebuild(self) -> int:
        self._store.truncate()
        indexed = 0
        for root in self._roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in self._extensions:
                    continue
                body = self._read_text(path)
                if body is None:
                    continue
                self._store.upsert(self._doc_id_for(path), body)
                indexed += 1
        self._store.optimize()
        return indexed

    @staticmethod
    def _read_text(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None

    def _doc_id_for(self, path: Path) -> str:
        try:
            return str(path.relative_to(self._vault_root))
        except ValueError:
            return str(path)

    def _resolve(self, root: str) -> Path:
        p = Path(root)
        return p if p.is_absolute() else self._vault_root / p
