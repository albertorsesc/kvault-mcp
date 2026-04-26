from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kvault_mcp.core.logger import make_logger

EventHandler = Callable[[str, dict[str, Any]], None]


def _handler_identity(handler: EventHandler) -> str:
    """Best-effort stable identifier for a handler, used in failure diagnostics."""
    owner = getattr(handler, "__self__", None)
    owner_repr = type(owner).__qualname__ if owner is not None else ""
    name = getattr(handler, "__qualname__", None) or getattr(handler, "__name__", "") or "<lambda>"
    module = getattr(handler, "__module__", "") or ""
    parts = [p for p in (module, owner_repr, name) if p]
    return ".".join(parts) if parts else repr(handler)


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[EventHandler]] = {}
        self._log = make_logger("kernel.eventbus")

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._subs.setdefault(event_type, []).append(handler)

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        handlers = list(self._subs.get(event_type, ()))
        for handler in handlers:
            try:
                handler(event_type, payload)
            except Exception:
                self._log.exception(
                    "event handler raised",
                    extra={
                        "event": event_type,
                        "plugin_id": _handler_identity(handler),
                    },
                )

    def handlers_for(self, event_type: str) -> list[EventHandler]:
        return list(self._subs.get(event_type, ()))
