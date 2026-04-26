from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kvault_mcp.kinds.audit import AuditReport, BaseAudit, Finding
from kvault_mcp.vault import iter_jsonl


class LineageDanglingAudit(BaseAudit):
    """Integrity audit: every lineage edge target must resolve to a framework row.

    Reads `lineage.jsonl` + `frameworks.jsonl` — so this audit runs after both
    manifests are built. A target is resolved when it matches a frameworks
    row's `title` or file `stem` (case-insensitive), or when a lineage-row's
    `target` exactly matches a frameworks row's `id`.
    """

    id = "audit.lineage_dangling"
    scope = "integrity"

    def __init__(self, kernel: Any) -> None:
        super().__init__(kernel)
        self._lineage_path = self._resolve(self.cfg["lineage_manifest"])
        self._frameworks_path = self._resolve(self.cfg["frameworks_manifest"])

    def run(self) -> AuditReport:
        started = _now()
        findings: list[Finding] = []
        if not self._lineage_path.exists() or not self._frameworks_path.exists():
            findings.append(
                Finding(
                    severity="info",
                    category="missing_manifest",
                    location=(
                        str(self._lineage_path)
                        if not self._lineage_path.exists()
                        else str(self._frameworks_path)
                    ),
                    message="required manifest missing; run manifest builders first",
                    fix_hint="Call manifest_builder.frameworks and manifest_builder.lineage.",
                )
            )
            return AuditReport(
                audit_id=self.id,
                started_at=started,
                finished_at=_now(),
                findings=findings,
                summary={"actionable_count": 0, "informational_count": len(findings)},
            )

        known = self._known_targets()
        for row in iter_jsonl(self._lineage_path):
            target = str(row.get("target", "")).strip()
            if not target:
                continue
            if target.lower() in known:
                continue
            findings.append(
                Finding(
                    severity="warning",
                    category="dangling_edge",
                    location=f"{row.get('source', '<unknown>')} -> [[{target}]]",
                    message=f"lineage target {target!r} does not appear in frameworks manifest",
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
            "vault.audit.lineage_dangling.completed",
            {"plugin_id": self.id, "finding_count": len(report.findings)},
        )
        return _report_to_dict(report)

    def _known_targets(self) -> set[str]:
        known: set[str] = set()
        for row in iter_jsonl(self._frameworks_path):
            if row.get("id"):
                known.add(str(row["id"]).lower())
            if row.get("title"):
                known.add(str(row["title"]).lower())
            if row.get("path"):
                stem = Path(str(row["path"])).stem
                known.add(stem.lower())
        return known

    def _resolve(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else self.vault_root / rel


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
