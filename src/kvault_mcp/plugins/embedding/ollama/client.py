from __future__ import annotations

import json
from typing import Any
from urllib import error, request


class OllamaHttpClient:
    """Stdlib HTTP client for Ollama's /api/embed and /api/tags endpoints.

    Responsibility: transport only. No batching, no dimension checks — those
    belong to the embedding plugin that composes this client.
    """

    def __init__(self, endpoint: str, timeout: float = 60.0) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._timeout = float(timeout)

    def embed(self, model: str, inputs: list[str]) -> list[list[float]]:
        body = json.dumps({"model": model, "input": inputs}).encode("utf-8")
        req = request.Request(
            url=f"{self._endpoint}/api/embed",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                payload: dict[str, Any] = json.loads(resp.read())
        except error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ollama HTTP {e.code}: {detail}") from e
        except error.URLError as e:
            raise RuntimeError(f"ollama unreachable: {e.reason}") from e

        vectors = payload.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(inputs):
            raise RuntimeError(f"unexpected response shape: {payload!r}")
        return vectors

    def model_exists(self, model: str) -> bool:
        try:
            with request.urlopen(f"{self._endpoint}/api/tags", timeout=5.0) as resp:
                data = json.loads(resp.read())
        except (error.URLError, TimeoutError):
            return False
        names = {m.get("name") for m in data.get("models", [])}
        return model in names or f"{model}:latest" in names

    @property
    def endpoint(self) -> str:
        return self._endpoint
