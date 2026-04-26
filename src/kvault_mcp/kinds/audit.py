from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from kvault_mcp.kinds._base import BasePlugin
from kvault_mcp.kinds._registry import register_provider_type


@dataclass
class Finding:
    severity: str  # "error" | "warning" | "info"
    category: str
    location: str
    message: str
    fix_hint: str | None = None


@dataclass
class AuditReport:
    audit_id: str
    started_at: str
    finished_at: str
    findings: list[Finding]
    summary: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Audit(Protocol):
    id: str
    scope: str  # "structural" | "content" | "integrity"

    def run(self) -> AuditReport: ...
    def health(self) -> dict[str, Any]: ...


class BaseAudit(BasePlugin):
    scope: str = "structural"

    def run(self) -> AuditReport:
        raise NotImplementedError


register_provider_type("audit", Audit)
