from __future__ import annotations

from typing import TypeVar

from kvault_mcp.core.logger import make_logger

P = TypeVar("P")


class ServiceRegistry:
    def __init__(self) -> None:
        self._instances: dict[type, list[tuple[str, object, bool]]] = {}
        self._log = make_logger("kernel.registry")

    def register(
        self,
        protocol: type,
        plugin_id: str,
        instance: object,
        active: bool,
    ) -> None:
        bucket = self._instances.setdefault(protocol, [])
        bucket.append((plugin_id, instance, active))

    def get_active(self, protocol: type[P]) -> P | None:
        bucket = self._instances.get(protocol, [])
        active = [item for item in bucket if item[2]]
        if not active:
            return None
        if len(active) > 1:
            self._log.warning(
                "multiple active providers; returning first",
                extra={"plugin_id": active[0][0]},
            )
        return active[0][1]  # type: ignore[return-value]

    def get_all(self, protocol: type[P]) -> list[P]:
        return [item[1] for item in self._instances.get(protocol, [])]  # type: ignore[misc]

    def registered(self) -> list[tuple[type, str, bool]]:
        out: list[tuple[type, str, bool]] = []
        for protocol, bucket in self._instances.items():
            for plugin_id, _, active in bucket:
                out.append((protocol, plugin_id, active))
        return out
