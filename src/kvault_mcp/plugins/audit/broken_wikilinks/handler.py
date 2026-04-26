from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kvault_mcp.kinds.audit import AuditReport, BaseAudit, Finding
from kvault_mcp.vault import extract_wikilinks, iter_markdown_files


class BrokenWikilinksAudit(BaseAudit):
    """Flags `[[wikilinks]]` whose target doesn't map to any markdown file.

    Resolution follows Obsidian's convention: the target is the file STEM
    (extension dropped), matched case-insensitively, and searched across the
    configured roots.
    """

    id = "audit.broken_wikilinks"
    scope = "structural"

    def __init__(self, kernel: Any) -> None:
        super().__init__(kernel)
        self._roots = list(self.cfg["roots"])
        self._extensions = tuple(self.cfg["extensions"])

    def run(self) -> AuditReport:
        started = _now()
        stems = self._index_stems()
        findings: list[Finding] = []
        for path in iter_markdown_files(self.vault_root, self._roots, self._extensions):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = self._relative(path)
            for link in extract_wikilinks(text):
                if link.target.lower() in stems:
                    continue
                findings.append(
                    Finding(
                        severity="warning",
                        category="broken_wikilink",
                        location=rel,
                        message=f"[[{link.target}]] has no matching note",
                        fix_hint=f"Create the target note or update the link in {rel}.",
                    )
                )
        finished = _now()
        return AuditReport(
            audit_id=self.id,
            started_at=started,
            finished_at=finished,
            findings=findings,
            summary={
                "actionable_count": len(findings),
                "informational_count": 0,
            },
        )

    def tool_run(self) -> dict[str, Any]:
        report = self.run()
        self.kernel.publish(
            "vault.audit.broken_wikilinks.completed",
            {"plugin_id": self.id, "finding_count": len(report.findings)},
        )
        return _report_to_dict(report)

    def _index_stems(self) -> set[str]:
        stems: set[str] = set()
        for path in iter_markdown_files(self.vault_root, self._roots, self._extensions):
            stems.add(path.stem.lower())
        return stems

    def _relative(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.vault_root))
        except ValueError:
            return str(path)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _report_to_dict(report: AuditReport) -> dict[str, Any]:
    return {
        "audit_id": report.audit_id,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "findings": [
            {
                "severity": f.severity,
                "category": f.category,
                "location": f.location,
                "message": f.message,
                "fix_hint": f.fix_hint,
            }
            for f in report.findings
        ],
        "summary": report.summary,
    }
