from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kvault_mcp.kinds.rule_store import BaseRuleStore, Rule
from kvault_mcp.vault import parse_frontmatter

_VALID_TYPES = {"user", "feedback", "project", "reference"}
_STATUSES = ("proposed", "active", "retired")


class MarkdownRuleStore(BaseRuleStore):
    """Markdown-file rule store under `memory/rules/{proposed,active,retired}/`.

    One file per rule. Frontmatter carries id/status/type/created/last_updated.
    Lifecycle mutations are file moves + frontmatter updates — atomic enough
    for a single-writer vault. Events emitted on every state change so the
    injector (or any other consumer) can refresh downstream artifacts.
    """

    id = "rule_store.markdown"

    def __init__(self, kernel: Any) -> None:
        super().__init__(kernel)
        for status in _STATUSES:
            self._dir(status).mkdir(parents=True, exist_ok=True)

    def propose(
        self,
        rule_id: str,
        title: str,
        body: str,
        rule_type: str,
        frontmatter: dict[str, Any] | None = None,
    ) -> Rule:
        self._validate_id(rule_id)
        if rule_type not in _VALID_TYPES:
            raise ValueError(
                f"rule_type must be one of {sorted(_VALID_TYPES)}, got {rule_type!r}"
            )
        now = _today()
        fm: dict[str, Any] = {
            "id": rule_id,
            "type": rule_type,
            "status": "proposed",
            "created": now,
            "last_updated": now,
        }
        if frontmatter:
            fm.update(frontmatter)
            fm["id"] = rule_id
            fm["type"] = rule_type
            fm["status"] = "proposed"
        path = self._dir("proposed") / f"{rule_id}.md"
        if path.exists() or self._path_for("active", rule_id).exists():
            raise FileExistsError(f"rule {rule_id!r} already exists")
        path.write_text(_render(title, body, fm), encoding="utf-8")
        self.kernel.publish(
            "vault.rule.proposed",
            {"plugin_id": self.id, "rule_id": rule_id, "path": str(path)},
        )
        return self._load(path)

    def approve(self, rule_id: str) -> Rule:
        src = self._path_for("proposed", rule_id)
        if not src.exists():
            raise FileNotFoundError(
                f"cannot approve {rule_id!r}: not in proposed/"
            )
        rule = self._load(src)
        dst = self._dir("active") / src.name
        self._move_with_status(src, dst, "active", rule)
        activated = self._load(dst)
        self.kernel.publish(
            "vault.rule.activated",
            {"plugin_id": self.id, "rule_id": rule_id, "path": str(dst)},
        )
        return activated

    def retire(self, rule_id: str, reason: str | None = None) -> Rule:
        for status in ("active", "proposed"):
            src = self._path_for(status, rule_id)
            if src.exists():
                break
        else:
            raise FileNotFoundError(f"cannot retire {rule_id!r}: not found")
        rule = self._load(src)
        dst = self._dir("retired") / src.name
        extra = {"retired_reason": reason} if reason else None
        self._move_with_status(src, dst, "retired", rule, extra_frontmatter=extra)
        retired = self._load(dst)
        self.kernel.publish(
            "vault.rule.retired",
            {"plugin_id": self.id, "rule_id": rule_id, "path": str(dst)},
        )
        return retired

    def get(self, rule_id: str) -> Rule | None:
        for status in _STATUSES:
            path = self._path_for(status, rule_id)
            if path.exists():
                return self._load(path)
        return None

    def list(self, status: str | None = None) -> list[Rule]:
        statuses = (status,) if status else _STATUSES
        out: list[Rule] = []
        for s in statuses:
            if s not in _STATUSES:
                raise ValueError(f"unknown status {s!r}")
            for path in sorted(self._dir(s).glob("*.md")):
                out.append(self._load(path))
        return out

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "counts": {s: len(list(self._dir(s).glob("*.md"))) for s in _STATUSES},
        }

    # ── internals ────────────────────────────────────────────────────────

    def _dir(self, status: str) -> Path:
        return self.kernel.state_path(f"rules.{status}")

    def _path_for(self, status: str, rule_id: str) -> Path:
        self._validate_id(rule_id)
        return self._dir(status) / f"{rule_id}.md"

    @staticmethod
    def _validate_id(rule_id: str) -> None:
        if not rule_id or not all(c.isalnum() or c in "_-." for c in rule_id):
            raise ValueError(f"invalid rule id: {rule_id!r}")

    def _load(self, path: Path) -> Rule:
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        title, body = _split_body(text)
        return Rule(
            id=str(fm.get("id", path.stem)),
            status=str(fm.get("status", path.parent.name)),
            rule_type=str(fm.get("type", "user")),
            title=title or path.stem,
            body=body,
            frontmatter=fm,
            source_path=str(path),
        )

    def _move_with_status(
        self,
        src: Path,
        dst: Path,
        new_status: str,
        rule: Rule,
        extra_frontmatter: dict[str, Any] | None = None,
    ) -> None:
        fm = dict(rule.frontmatter)
        fm["status"] = new_status
        fm["last_updated"] = _today()
        if extra_frontmatter:
            fm.update(extra_frontmatter)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(_render(rule.title, rule.body, fm), encoding="utf-8")
        src.unlink()


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _split_body(text: str) -> tuple[str, str]:
    """Return (title_from_first_h1, body_after_frontmatter+title)."""
    after_fm = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            after_fm = text[end + len("\n---\n"):]
    lines = after_fm.lstrip("\n").splitlines()
    title = ""
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            body_start = i + 1
            break
    body = "\n".join(lines[body_start:]).lstrip("\n")
    return title, body


def _render(title: str, body: str, frontmatter: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in frontmatter.items():
        lines.append(f"{key}: {_render_scalar(value)}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    if body:
        lines.append(body.rstrip() + "\n")
    return "\n".join(lines)


def _render_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "[" + ", ".join(_render_scalar(v) for v in value) + "]"
    s = str(value)
    if any(ch in s for ch in ":#'\"") or s.strip() != s:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s
