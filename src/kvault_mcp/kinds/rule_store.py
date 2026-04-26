from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from kvault_mcp.kinds._base import BasePlugin
from kvault_mcp.kinds._registry import register_provider_type


@dataclass
class Rule:
    """Persisted representation of a single rule."""

    id: str
    status: str                     # "proposed" | "active" | "retired"
    rule_type: str                  # "user" | "feedback" | "project" | "reference"
    title: str
    body: str
    frontmatter: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""


@runtime_checkable
class RuleStore(Protocol):
    id: str

    def propose(
        self,
        rule_id: str,
        title: str,
        body: str,
        rule_type: str,
        frontmatter: dict[str, Any] | None = None,
    ) -> Rule: ...
    def approve(self, rule_id: str) -> Rule: ...
    def retire(self, rule_id: str, reason: str | None = None) -> Rule: ...
    def get(self, rule_id: str) -> Rule | None: ...
    def list(self, status: str | None = None) -> list[Rule]: ...
    def health(self) -> dict[str, Any]: ...


class BaseRuleStore(BasePlugin):
    """Scaffolding for rule store implementations.

    Subclasses override the CRUD methods. `tool_*` helpers below serialize
    Rule objects to dicts for MCP tool responses — no subclass needs to
    duplicate that.
    """

    def propose(
        self,
        rule_id: str,
        title: str,
        body: str,
        rule_type: str,
        frontmatter: dict[str, Any] | None = None,
    ) -> Rule:
        raise NotImplementedError

    def approve(self, rule_id: str) -> Rule:
        raise NotImplementedError

    def retire(self, rule_id: str, reason: str | None = None) -> Rule:
        raise NotImplementedError

    def get(self, rule_id: str) -> Rule | None:
        raise NotImplementedError

    def list(self, status: str | None = None) -> list[Rule]:
        raise NotImplementedError

    @staticmethod
    def _rule_to_dict(rule: Rule) -> dict[str, Any]:
        return {
            "id": rule.id,
            "status": rule.status,
            "type": rule.rule_type,
            "title": rule.title,
            "body": rule.body,
            "frontmatter": rule.frontmatter,
            "source_path": rule.source_path,
        }

    def tool_propose(
        self,
        rule_id: str,
        title: str,
        body: str,
        rule_type: str,
        frontmatter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rule = self.propose(rule_id, title, body, rule_type, frontmatter)
        return self._rule_to_dict(rule)

    def tool_approve(self, rule_id: str) -> dict[str, Any]:
        return self._rule_to_dict(self.approve(rule_id))

    def tool_retire(self, rule_id: str, reason: str | None = None) -> dict[str, Any]:
        return self._rule_to_dict(self.retire(rule_id, reason=reason))

    def tool_list(self, status: str | None = None) -> list[dict[str, Any]]:
        return [self._rule_to_dict(r) for r in self.list(status=status)]


register_provider_type("rule_store", RuleStore)
