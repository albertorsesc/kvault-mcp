from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from kvault_mcp.kinds._base import BasePlugin
from kvault_mcp.kinds._registry import register_provider_type
from kvault_mcp.kinds._types import RetrievalResult


@runtime_checkable
class Retriever(Protocol):
    id: str

    def query(self, situation: str, k: int = 5) -> list[RetrievalResult]: ...
    def health(self) -> dict[str, Any]: ...


class BaseRetriever(BasePlugin):
    """Subclasses override `query`. `tool_search` is the shared MCP adapter."""

    def query(self, situation: str, k: int = 5) -> list[RetrievalResult]:
        raise NotImplementedError

    def tool_search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.query(query, k=k)]


register_provider_type("retriever", Retriever)
