# Manifests

A manifest is a durable, derived JSONL file that reflects some aspect of the vault. Manifests are built by plugins, consumed by other plugins, and regenerable from source. They are the vault's index layer.

## Principles

- **Derived, never authored.** A manifest can be deleted and rebuilt without data loss.
- **Append-friendly.** Most manifests are JSONL so incremental appenders don't rewrite the whole file.
- **Schema-bound.** Every manifest has a JSON Schema under `schemas/`; every line validates against it.
- **Plugin-owned.** Each manifest has exactly one producer plugin. Other plugins read, they do not write.

## Standard manifests

Shipped plugins produce these. The list is not fixed — any plugin can ship a manifest.

| File | Producer | Purpose |
|---|---|---|
| `memory/semantic/vault-capabilities.jsonl` | `build-capabilities-registry` | Installed plugins + active state + health |
| `memory/semantic/lineage.jsonl` | `build-lineage-manifest` | Graph of entities citing other entities |
| `memory/semantic/frameworks.jsonl` | `build-frameworks-manifest` | Named frameworks with source notes |
| `memory/semantic/proposals.jsonl` | `consolidation` | Proposals awaiting human review |
| `memory/semantic/incidents.jsonl` | Any plugin | Anomalies observed during operation |
| `memory/episodic/run-log.jsonl` | Kernel (via `log-capability-run`) | Every tool invocation |

Additional manifests can be introduced by plugins. The kernel doesn't care what they are — only that they live under `memory/` and declare a schema.

## Schemas

Schemas live in `<plugin>/schemas/*.json` for plugins that ship them, or in a shared `kvault.plugins/schemas/` directory for common schemas.

Every manifest line must validate against its schema. The `audit-schemas` plugin (shipped) runs this check on every audit pass. Invalid lines are findings, not silent corruption.

## Building

Manifest builder plugins are idempotent. They:

1. Read all relevant source data (notes, plugin registrations, other manifests).
2. Build the desired state in memory.
3. Write atomically to a temp file, then rename over the target. No half-written state ever visible.
4. Emit `vault.manifest.<name>.built` with counts.

Rebuild cost is the entire source scan — so builders are invoked on demand (via MCP tool), not continuously. Incremental manifests are possible but optional; simple full rebuilds are the default.

## Consumption

A plugin consuming a manifest:

1. Opens the JSONL file via `kernel.state_path(...)`.
2. Streams lines, parsing each as JSON.
3. Handles missing file gracefully (manifest not built yet is a valid state).

Never assume a manifest is present. Never assume it's current. If currency matters, the consumer should invoke the builder first or read the builder's last-run timestamp from the run-log.

## Atomicity

JSONL append from multiple producers is unsafe on POSIX without locking. The rule:

- **Full-rebuild manifests** (capabilities, lineage, frameworks) — rewritten atomically via temp + rename. No append contention.
- **Append-only manifests** (run-log, incidents) — one producer per file. The kernel's `log-capability-run` is the only writer of `run-log.jsonl`. If multiple plugins need to append, they route through an event consumer that owns the file.

## Retention

Manifest retention is per-file policy:

- Full-rebuild manifests: no retention — each build replaces. Previous state is in git if committed.
- `run-log.jsonl`: rotated by the `rotate-run-log` plugin when it exceeds a threshold; old entries archived to dated backups; backups beyond retention pruned.
- `proposals.jsonl`: append-only; pruning on human decision (approve/reject cycle moves proposals elsewhere).
- `incidents.jsonl`: append-only; periodic archival to dated files is a plugin policy.

## Building a new manifest

To ship a new manifest:

1. Define the schema (`<plugin>/schemas/<name>.json`).
2. Pick a path (`memory/semantic/<name>.jsonl` by convention).
3. Write a builder plugin that reads sources and writes the file atomically.
4. Emit `vault.manifest.<name>.built` on success.
5. Register the schema with `audit-schemas` (by putting it under the shared schemas dir).

Other plugins can now consume the new manifest by path. No kernel changes required.

## What a manifest is not

- Not a database. No queries, no indexes, no transactions. Just lines.
- Not authoritative. A manifest is a projection of source data. If source and manifest disagree, source wins.
- Not a cache. Manifests are regenerable, but they're first-class derived state, not transient. A cache lives under `memory/working/`.
