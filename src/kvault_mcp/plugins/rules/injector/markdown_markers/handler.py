from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kvault_mcp.kinds.rule_injector import BaseRuleInjector
from kvault_mcp.kinds.rule_store import Rule, RuleStore

START_MARKER = "<!-- kvault:rules:start -->"
END_MARKER = "<!-- kvault:rules:end -->"
_BLOCK_RE = re.compile(
    re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
    re.DOTALL,
)


class MarkdownMarkersInjector(BaseRuleInjector):
    """Renders active rules into a markdown file between HTML comment markers.

    Never touches content outside the markers. If the markers are missing, the
    block is appended to the target file (or the file is created when
    `create_if_missing = true`). Pulls rules from the active `RuleStore` via
    the kernel registry — no plugin-to-plugin imports.
    """

    id = "rule_injector.markdown_markers"

    def __init__(self, kernel: Any) -> None:
        super().__init__(kernel)
        target = Path(self.cfg["target"])
        self._target = target if target.is_absolute() else self.vault_root / target
        self._heading = str(self.cfg["heading"])
        self._create_if_missing = bool(self.cfg["create_if_missing"])

    def inject(self) -> dict[str, Any]:
        store = self.kernel.get_active(RuleStore)
        if store is None:
            return {"ok": False, "reason": "no active rule_store", "written": False}
        rules = store.list(status="active")
        block = _render_block(self._heading, rules)
        return self._write_block(block, rule_count=len(rules))

    def health(self) -> dict[str, Any]:
        store = self.kernel.get_active(RuleStore)
        return {
            "ok": store is not None,
            "target": str(self._target),
            "target_exists": self._target.exists(),
            "store_available": store is not None,
        }

    # subscriber methods — wired by kernel when consumes_events lists them
    def on_vault_rule_activated(self, _event: str, _payload: dict[str, Any]) -> None:
        self.inject()

    def on_vault_rule_retired(self, _event: str, _payload: dict[str, Any]) -> None:
        self.inject()

    # ── internals ────────────────────────────────────────────────────────

    def _write_block(self, block: str, rule_count: int) -> dict[str, Any]:
        if not self._target.exists():
            if not self._create_if_missing:
                return {
                    "ok": False,
                    "reason": f"target {self._target} does not exist",
                    "written": False,
                }
            self._target.parent.mkdir(parents=True, exist_ok=True)
            self._target.write_text(block + "\n", encoding="utf-8")
            self._publish(rule_count)
            return {"ok": True, "written": True, "target": str(self._target)}

        original = self._target.read_text(encoding="utf-8")
        if _BLOCK_RE.search(original):
            new = _BLOCK_RE.sub(block, original, count=1)
        else:
            sep = "" if original.endswith("\n") else "\n"
            new = f"{original}{sep}\n{block}\n"
        if new != original:
            self._target.write_text(new, encoding="utf-8")
        self._publish(rule_count)
        return {
            "ok": True,
            "written": new != original,
            "target": str(self._target),
            "rule_count": rule_count,
        }

    def _publish(self, rule_count: int) -> None:
        self.kernel.publish(
            "vault.rules.injected",
            {
                "plugin_id": self.id,
                "target": str(self._target),
                "rule_count": rule_count,
            },
        )


def _render_block(heading: str, rules: list[Rule]) -> str:
    lines = [
        START_MARKER,
        "<!-- Rendered by kvault-mcp. Do not edit between these markers by hand. -->",
        "",
        heading,
        "",
    ]
    if not rules:
        lines.append("_No active rules._")
    else:
        for rule in rules:
            summary = rule.body.strip().splitlines()[0] if rule.body.strip() else ""
            suffix = f" — {summary}" if summary else ""
            lines.append(f"- **{rule.title}**{suffix} [{rule.id}]")
    lines.append("")
    lines.append(END_MARKER)
    return "\n".join(lines)
