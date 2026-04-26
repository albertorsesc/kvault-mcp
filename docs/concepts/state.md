# State

All mutable state lives inside the target vault. The kernel and plugins are stateless code. If you delete the kvault-mcp install and reinstall, no information is lost — everything meaningful is in the vault.

## Why

- Multi-vault operation: one kernel serves N vaults, each with its own state.
- Safe reinstall: upgrade or reinstall the package without data migration.
- Debuggability: state is on disk, inspectable with any text tool.
- Portability: the vault is the unit that moves between machines; its state moves with it.

## State directories inside the vault

```
<vault>/
├── memory/
│   ├── episodic/
│   │   ├── run-log.jsonl                 # every tool invocation (append-only; rotated)
│   │   └── YYYY-MM-DD-<slug>.md          # episodic events (experiments, incidents)
│   ├── semantic/
│   │   ├── vault-capabilities.jsonl      # registry of installed plugins + active state
│   │   ├── lineage.jsonl                 # graph of who-cites-whom across vault entities
│   │   ├── proposals.jsonl               # consolidation output awaiting human review
│   │   ├── incidents.jsonl               # anomaly records produced during operation
│   │   └── vectors.db                    # (if a vector_store plugin is active) embedding collections
│   ├── working/                          # ephemeral, session-scoped files
│   └── personal/                         # user preferences, stays local per Constraint Escalation
├── memory/rules/
│   ├── proposed/<id>.md                  # captured rule candidates
│   ├── active/<id>.md                    # approved + injected
│   └── retired/<id>.md                   # archived
├── kvault.config.toml                    # per-vault config
└── kvault.plugins/<kind>/<name>/         # vault-local plugins
```

## Ownership

Files come in two categories:

| Category | Who writes | Who reads |
|---|---|---|
| **Derived** (manifests, run-log, reports) | Kernel + plugins | Anyone |
| **Authored** (hubs, source notes, rules, config) | Humans (or agents on behalf of humans) | Anyone |

Derived files can be deleted and rebuilt. Authored files should not be modified by tools without explicit operations (e.g., rule injection). The `validate-vault-write` hook enforces structural rules on authored files.

## Path resolution

Plugins never hardcode paths. They call:

```python
self.kernel.state_path("episodic", "run-log.jsonl")
# returns <vault>/memory/episodic/run-log.jsonl
```

Known categories:

- `"episodic"` → `memory/episodic/`
- `"semantic"` → `memory/semantic/`
- `"working"` → `memory/working/`
- `"personal"` → `memory/personal/`
- `"rules.proposed"` → `memory/rules/proposed/`
- `"rules.active"` → `memory/rules/active/`
- `"rules.retired"` → `memory/rules/retired/`

Adding a new category is a kernel change (rare).

## Manifest + run-log schemas

Every durable JSONL state file has a JSON Schema under `schemas/`. The `audit-schemas` plugin validates every line of every manifest against its schema on each audit run. Schema drift is a finding, never silent corruption.

## Retention

- `run-log.jsonl` — rotated by the `rotate-run-log` plugin when it exceeds a configurable threshold. Old entries archived to dated backups; backups older than retention are pruned.
- Derived manifests (`vault-capabilities.jsonl`, `lineage.jsonl`) — rebuilt from scratch each time; no retention concern.
- `proposals.jsonl` — append-only; pruning is a separate operation if it grows.
- `vectors.db` — keeps multiple versioned collections (see [`retrieval.md`](retrieval.md)); oldest pruned on explicit `vault.embeddings.prune` call.
- Rule files (`memory/rules/`) — retained indefinitely; retired rules stay in `retired/` for history.

## What's not in state

- No cache of external resource contents (e.g., fetched web pages). If a plugin needs caching, it manages its own cache file under `memory/working/` with the plugin's ID as a prefix.
- No secrets. API keys, tokens, etc. come from environment variables or OS keychains. Never written to vault state.
- No user PII beyond what the user chose to put in hubs/notes. State files do not capture user input verbatim.
