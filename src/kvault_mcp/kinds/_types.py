from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievalResult:
    """Result of a retrieval call. Used by Retriever, VectorStore, and TextIndex."""

    id: str
    score: float
    snippet: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "score": self.score,
            "snippet": self.snippet,
            "metadata": self.metadata,
        }
