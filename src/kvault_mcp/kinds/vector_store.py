from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from kvault_mcp.kinds._base import BasePlugin
from kvault_mcp.kinds._registry import register_provider_type
from kvault_mcp.kinds._types import RetrievalResult


@runtime_checkable
class VectorStore(Protocol):
    id: str

    def collection_create(self, collection_id: str, dimensions: int) -> None: ...
    def collection_list(self) -> list[dict[str, Any]]: ...
    def add(self, collection_id: str, items: list[dict[str, Any]]) -> None: ...
    def query(
        self, collection_id: str, vector: list[float], k: int = 5
    ) -> list[RetrievalResult]: ...
    def health(self) -> dict[str, Any]: ...


class BaseVectorStore(BasePlugin):
    def collection_create(self, collection_id: str, dimensions: int) -> None:
        raise NotImplementedError

    def collection_list(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def add(self, collection_id: str, items: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    def query(
        self, collection_id: str, vector: list[float], k: int = 5
    ) -> list[RetrievalResult]:
        raise NotImplementedError


register_provider_type("vector_store", VectorStore)
