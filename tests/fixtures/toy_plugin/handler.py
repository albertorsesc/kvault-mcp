from __future__ import annotations

from typing import Any


class ToyRetriever:
    id = "toy"

    def __init__(self, kernel: Any) -> None:
        self.kernel = kernel
        self.cfg = kernel.config("retriever.toy")
        self.pings_received = 0

    def query(self, situation: str, k: int = 5) -> list[dict[str, Any]]:
        greeting = self.cfg.get("greeting", "hello")
        return [{"id": "toy:1", "score": 1.0, "snippet": f"{greeting} {situation}", "metadata": {}}]

    def health(self) -> dict[str, Any]:
        return {"ok": True, "greeting": self.cfg.get("greeting")}

    def echo(self, **kwargs: Any) -> dict[str, Any]:
        return {"echoed": kwargs, "from": self.id}

    def on_vault_toy_ping(self, event_type: str, payload: dict[str, Any]) -> None:
        self.pings_received += 1
