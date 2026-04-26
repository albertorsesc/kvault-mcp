from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from kvault_mcp.kinds._base import BasePlugin
from kvault_mcp.kinds._registry import register_provider_type


@runtime_checkable
class EmbeddingProvider(Protocol):
    id: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def health(self) -> dict[str, Any]: ...


class BaseEmbeddingProvider(BasePlugin):
    """Template Method base. Subclass overrides `_embed_batch`; batching is free."""

    dimensions: int = 0
    batch_size: int = 32

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            out.extend(self._embed_batch(texts[start:start + self.batch_size]))
        return out

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        raise NotImplementedError


register_provider_type("embedding_provider", EmbeddingProvider)
