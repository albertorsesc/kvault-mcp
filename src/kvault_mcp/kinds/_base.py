from __future__ import annotations

import logging
from pathlib import Path
from typing import Any


class BasePlugin:
    """Shared init scaffolding for every plugin.

    Closed for modification, open for extension. Subclasses MUST set the class
    attribute `id` to the canonical plugin id (`<kind>.<name>`, e.g.
    `"embedding.ollama"`). On `super().__init__(kernel)` they receive
    `self.kernel`, `self.cfg`, `self.log`, `self.vault_root`.
    """

    id: str = ""

    def __init__(self, kernel: Any) -> None:
        if not self.id:
            raise ValueError(
                f"{type(self).__name__} must set class attribute `id`"
            )
        self.kernel = kernel
        self.cfg: dict[str, Any] = kernel.config(self.id)
        self.log: logging.Logger = kernel.logger(self.id)
        self.vault_root: Path = kernel.vault_root()

    def health(self) -> dict[str, Any]:
        return {"ok": True}
