from __future__ import annotations

from typing import Any

from kvault_mcp.kinds._types import RetrievalResult
from kvault_mcp.kinds.retriever import BaseRetriever
from kvault_mcp.kinds.text_index import TextIndex


class FtsOnlyRetriever(BaseRetriever):
    """Retriever that delegates every query to the active TextIndex.

    Owns no storage. Pulls the active TextIndex from the kernel registry on
    each call — loose coupling, hot-swappable.
    """

    id = "retriever.fts_only"

    def query(self, situation: str, k: int = 5) -> list[RetrievalResult]:
        text_index = self.kernel.get_active(TextIndex)
        if text_index is None:
            return []
        return text_index.search(situation, k=k)

    def health(self) -> dict[str, Any]:
        has_index = self.kernel.get_active(TextIndex) is not None
        return {"ok": has_index, "text_index_available": has_index}
