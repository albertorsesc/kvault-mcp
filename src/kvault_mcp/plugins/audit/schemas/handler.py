from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from kvault_mcp.kinds.audit import AuditReport, BaseAudit, Finding
from kvault_mcp.vault import iter_jsonl


class SchemasAudit(BaseAudit):
    """Validates every JSONL manifest against its registered JSON Schema.

    Surfaces each bad line as a `structural/invalid_schema` finding with the
    exact file and line number. A missing schema target is also a finding —
    silent drift is the failure mode we want to prevent.
    """

    id = "audit.schemas"
    scope = "structural"

    def __init__(self, kernel: Any) -> None:
        super().__init__(kernel)
        self._targets: dict[str, str] = dict(self.cfg.get("targets", {}))

    def run(self) -> AuditReport:
        started = _now()
        findings: list[Finding] = []
        total_lines = 0
        for manifest_rel, schema_rel in self._targets.items():
            manifest_path = self._resolve(manifest_rel)
            schema_path = self._resolve(schema_rel)
            if not schema_path.exists():
                findings.append(
                    Finding(
                        severity="error",
                        category="missing_schema",
                        location=str(schema_path),
                        message=f"schema for {manifest_rel!r} not found at {schema_path}",
                    )
                )
                continue
            if not manifest_path.exists():
                continue  # an absent manifest is not a failure — builder may not have run yet
            try:
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                findings.append(
                    Finding(
                        severity="error",
                        category="invalid_schema_file",
                        location=str(schema_path),
                        message=f"schema file unreadable or malformed: {exc}",
                    )
                )
                continue
            validator = Draft202012Validator(schema)
            for line_no, row in _safe_iter_jsonl(manifest_path, findings):
                total_lines += 1
                for err in validator.iter_errors(row):
                    path = "/".join(map(str, err.absolute_path)) or "<root>"
                    findings.append(
                        Finding(
                            severity="error",
                            category="invalid_schema",
                            location=f"{manifest_rel}:{line_no}:{path}",
                            message=err.message,
                            fix_hint=f"Ensure row {line_no} in {manifest_rel} matches {schema_rel}.",
                        )
                    )

        finished = _now()
        actionable = sum(1 for f in findings if f.severity == "error")
        return AuditReport(
            audit_id=self.id,
            started_at=started,
            finished_at=finished,
            findings=findings,
            summary={
                "lines_validated": total_lines,
                "actionable_count": actionable,
                "informational_count": len(findings) - actionable,
            },
        )

    def tool_run(self) -> dict[str, Any]:
        report = self.run()
        self.kernel.publish(
            "vault.audit.schemas.completed",
            {"plugin_id": self.id, "finding_count": len(report.findings)},
        )
        return _report_to_dict(report)

    def _resolve(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else self.vault_root / rel


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_iter_jsonl(path: Path, findings: list[Finding]):
    try:
        with path.open(encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    yield line_no, json.loads(raw)
                except json.JSONDecodeError as exc:
                    findings.append(
                        Finding(
                            severity="error",
                            category="invalid_json",
                            location=f"{path}:{line_no}",
                            message=str(exc),
                        )
                    )
    except OSError as exc:
        findings.append(
            Finding(
                severity="error",
                category="unreadable_manifest",
                location=str(path),
                message=str(exc),
            )
        )


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


# re-export module-level helper used by other audit handlers
iter_jsonl = iter_jsonl
