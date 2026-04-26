# Audits

An audit is a read-only plugin that inspects vault state and emits findings. Audits never modify the vault. They are the vault's immune system.

## Shape of an audit

Every audit implements the same protocol:

```python
class Audit(Protocol):
    id: str                          # stable audit ID
    scope: str                       # "structural" | "content" | "integrity"
    def run(self) -> AuditReport: ...
    def health(self) -> dict: ...
```

`AuditReport`:

```python
@dataclass
class AuditReport:
    audit_id: str
    started_at: str                  # ISO 8601
    finished_at: str
    findings: list[Finding]
    summary: dict                    # counts, categories, etc.

@dataclass
class Finding:
    severity: str                    # "error" | "warning" | "info"
    category: str                    # audit-specific taxonomy
    location: str                    # file path, line, or logical identifier
    message: str                     # human-readable
    fix_hint: str | None             # optional remediation suggestion
```

Findings are structured. Plugins and humans both read them. The kernel does not interpret them — it just collects, logs, and routes.

## Scope categories

- **structural** — violations the kernel can enforce mechanically (missing required files, bad frontmatter, broken wikilinks, schema-invalid JSONL lines).
- **content** — higher-level violations about what the content says (orphan notes, stale references, unresolved TODOs).
- **integrity** — consistency across manifests (dangling lineage edges, capability registry divergent from actual installs).

Scope is advisory. An audit chooses its own scope; the kernel doesn't enforce the taxonomy.

## Running audits

Audits are invoked explicitly:

```
kvault.audit.run id=audit-broken-wikilinks
kvault.audit.run-all
```

There is no background audit daemon. Audits run when requested — by the assistant, by a human, or by a scheduler external to kvault-mcp.

`run-all` invokes every registered audit in parallel (or sequentially, per kernel config) and aggregates findings into a single report.

## Actionable vs informational

An audit declares in its report whether findings are **actionable** (CI should fail, human should fix) or **informational** (surfaced for awareness, not a gate).

```python
summary = {
    "actionable_count": 3,
    "informational_count": 12,
}
```

The kernel exposes both counts in the aggregated report. Downstream tooling (commit hooks, dashboards) can gate on actionable counts alone.

## Findings format on disk

When `audit-all` runs, it writes a dated findings file:

```
memory/semantic/audit-findings/YYYY-MM-DD.md
```

One file per day. Appended to if run multiple times. Format:

```markdown
# Findings — 2026-04-22

## audit-broken-wikilinks (scope: structural)

- [ ] **error** · `AI/2026-04-15-foo.md` → broken wikilink `[[nonexistent-framework]]`
- [ ] **warning** · `Frameworks/Bar.md` → wikilink `[[old-name]]` resolves via alias; prefer canonical

## audit-schemas (scope: structural)

(no findings)
```

This is derived state — regeneratable — but retained as a human-readable trail.

## Writing a new audit

1. Implement the `Audit` protocol.
2. Declare `scope` and `id`.
3. Emit findings with stable categories (don't invent new ones per run).
4. Return quickly if nothing to check; audits should be cheap.
5. Register via plugin manifest with `kind = "audit"`.

The kernel picks it up and it appears in `run-all`.

## What audits don't do

- **No fixes.** An audit never writes to the vault. A separate plugin can consume findings and propose fixes, but audits themselves are strictly read-only.
- **No cross-audit orchestration.** An audit doesn't invoke other audits. The `run-all` orchestrator is the kernel's job.
- **No state beyond findings.** An audit's only output is its report. It does not maintain its own cache or history.

## Shipped audits

The initial package ships a minimal set; more are added over time:

| Audit ID | Scope | What it checks |
|---|---|---|
| `audit-schemas` | structural | Every JSONL line under `memory/` validates against its schema |
| `audit-broken-wikilinks` | structural | All `[[wikilinks]]` resolve to existing notes |
| `audit-lineage-dangling` | integrity | Every lineage edge references an entity that exists |
| `audit-orphan-notes` | content | Notes not referenced by any hub or index |
| `audit-capability-registry` | integrity | Registered plugins match discovered plugins |

All audits are optional. Running none is a valid configuration (though not recommended).
