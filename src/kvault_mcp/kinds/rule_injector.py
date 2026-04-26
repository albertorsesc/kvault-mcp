from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from kvault_mcp.kinds._base import BasePlugin
from kvault_mcp.kinds._registry import register_provider_type


@runtime_checkable
class RuleInjector(Protocol):
    id: str

    def inject(self) -> dict[str, Any]: ...
    def health(self) -> dict[str, Any]: ...


class BaseRuleInjector(BasePlugin):
    """Renders active rules into some assistant-visible surface.

    Concrete injectors might write to CLAUDE.md between HTML markers, to a
    JSON-backed settings file, or over HTTP to a remote agent-config API.
    They all expose `inject()` and nothing else — ISP-narrow by design.
    """

    def inject(self) -> dict[str, Any]:
        raise NotImplementedError

    def tool_inject(self) -> dict[str, Any]:
        return self.inject()


register_provider_type("rule_injector", RuleInjector)
