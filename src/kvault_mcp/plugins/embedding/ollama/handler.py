from __future__ import annotations

from typing import Any

from kvault_mcp.kinds.embedding import BaseEmbeddingProvider
from kvault_mcp.plugins.embedding.ollama.client import OllamaHttpClient


class OllamaEmbedding(BaseEmbeddingProvider):
    """Ollama HTTP embedding provider.

    Plugin class. Config → client. Batching + dimension enforcement inherited
    from `BaseEmbeddingProvider` (Template Method). Transport is `OllamaHttpClient`.
    """

    id = "embedding.ollama"

    def __init__(self, kernel: Any) -> None:
        super().__init__(kernel)
        self._model: str = str(self.cfg["model"])
        self.dimensions = int(self.cfg["dimensions"])
        self.batch_size = int(self.cfg["batch_size"])
        self._client = OllamaHttpClient(
            endpoint=str(self.cfg["endpoint"]),
            timeout=float(self.cfg["timeout"]),
        )

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        vectors = self._client.embed(self._model, batch)
        for v in vectors:
            if len(v) != self.dimensions:
                raise RuntimeError(
                    f"dimension mismatch: config={self.dimensions} response={len(v)}"
                )
        return vectors

    def health(self) -> dict[str, Any]:
        pulled = self._client.model_exists(self._model)
        return {
            "ok": pulled,
            "endpoint": self._client.endpoint,
            "model": self._model,
            "dimensions": self.dimensions,
            "model_pulled": pulled,
        }
