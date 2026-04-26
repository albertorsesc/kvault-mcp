from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from kvault_mcp.kinds._base import BasePlugin
from kvault_mcp.kinds._registry import register_provider_type
from kvault_mcp.kinds._types import RetrievalResult


@runtime_checkable
class TextIndex(Protocol):
    id: str

    def index(
        self, doc_id: str, text: str, metadata: dict[str, Any] | None = None
    ) -> None: ...
    def delete(self, doc_id: str) -> None: ...
    def search(self, query: str, k: int = 10) -> list[RetrievalResult]: ...
    def rebuild(self) -> dict[str, Any]: ...
    def health(self) -> dict[str, Any]: ...


class BaseTextIndex(BasePlugin):
    """Subclasses override index/delete/search/rebuild. Shared MCP tool adapters below."""

    def index(
        self, doc_id: str, text: str, metadata: dict[str, Any] | None = None
    ) -> None:
        raise NotImplementedError

    def delete(self, doc_id: str) -> None:
        raise NotImplementedError

    def search(self, query: str, k: int = 10) -> list[RetrievalResult]:
        raise NotImplementedError

    def rebuild(self) -> dict[str, Any]:
        raise NotImplementedError

    def tool_search(self, query: str, k: int = 10) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.search(query, k=k)]

    def tool_rebuild(self) -> dict[str, Any]:
        return self.rebuild()


register_provider_type("text_index", TextIndex)
