# Architecture

The meta architecture of kvault-mcp. One page. Every other doc elaborates a piece of this.

## Design invariants

These are not goals. They are hard rules the architecture is measured against.

1. **The kernel has zero plugins baked in.** No audit, retriever, embedding provider, or hook is imported by kernel code. Everything is discovered.
2. **No plugin imports another plugin.** Plugins interact only through the kernel's service registry (synchronous) or event bus (asynchronous). A plugin's code has no knowledge of any other plugin's existence.
3. **Adding a new plugin never requires a kernel change.** Drop a directory, restart, it works.
4. **All state lives in the target vault.** The kernel and its plugins are stateless code. Nothing meaningful is kept outside the vault being operated on.
5. **Every plugin declares its contract.** A machine-readable `plugin.toml` states what protocol it implements, what events it emits and consumes, and what config it expects.
6. **All behavior change is proposed, not applied.** Rules, learnings, and policies surface as proposals that a human approves. Nothing auto-mutates the vault.

## Layers

```
┌────────────────────────────────────────────────────┐
│  MCP client (Claude Code, Cursor, Desktop, etc.)   │
└──────────────────────────┬─────────────────────────┘
                           │ MCP protocol (stdio/SSE)
                           ▼
┌────────────────────────────────────────────────────┐
│  Kernel                                            │
│    - Plugin discovery (entry points + dirs)        │
│    - Service registry (sync protocol lookup)       │
│    - Event bus (async pub/sub)                     │
│    - Config loader + schema validation             │
│    - Lifecycle (load, health, start, stop)         │
│    - MCP wiring (tool + resource registration)     │
└──────────────────────────┬─────────────────────────┘
                           │ protocols
                           ▼
┌────────────────────────────────────────────────────┐
│  Plugins (all equal; no hierarchy)                 │
│                                                    │
│    embedding/        retriever/      audit/        │
│    vector_store/     reranker/       hook/         │
│    manifest/         rule_source/    consolidator/ │
│    policy_provider/  tool/           ...           │
└────────────────────────────────────────────────────┘
                           │ reads / writes
                           ▼
┌────────────────────────────────────────────────────┐
│  Vault (the subject)                               │
│    - content: Frameworks/, topic dirs, source notes│
│    - state:   memory/{episodic, semantic, working} │
│    - config:  kvault.config.toml                   │
│    - plugins: kvault.plugins/<kind>/<name>/        │
└────────────────────────────────────────────────────┘
```

## Two coordination patterns

Plugins never call each other directly. They coordinate through the kernel:

**Service registry** — synchronous, protocol-based. A plugin asks the kernel *"give me the active plugin that implements Retriever"* and gets it back. Used for in-tool composition (e.g., an MCP tool handler needs a retriever to answer a query). See [`concepts/service-registry.md`](concepts/service-registry.md).

**Event bus** — asynchronous, topic-based. A plugin publishes `vault.audit.completed`; any plugin that subscribes reacts independently. Used for workflows (consolidation, rule capture, reacting to state changes). See [`concepts/events.md`](concepts/events.md).

The dual model is intentional. Sync lookup keeps tool semantics simple; async events keep workflows decoupled.

## Plugin kinds

Plugins are organized by kind. Each kind has a protocol the plugin must implement.

| Kind | Protocol | What it does |
|---|---|---|
| `embedding` | `EmbeddingProvider` | Turns text into vectors |
| `vector_store` | `VectorStore` | Persists and queries vectors |
| `reranker` | `Reranker` | Reorders retrieved candidates |
| `retriever` | `Retriever` | Assembles a query pipeline (may compose the above, or be monolithic) |
| `manifest` | `ManifestBuilder` | Produces a durable state file from vault contents |
| `audit` | `Audit` | Inspects vault state, emits findings |
| `rule_source` | `RuleSource` | Captures rule candidates (from conversations, patterns, explicit input) |
| `consolidator` | `Consolidator` | Surfaces patterns from episodic logs as proposals |
| `policy_provider` | `PolicyProvider` | Resolves a named policy to a concrete value + source citation |
| `hook` | `Hook` | Called by an external runtime (e.g., Claude Code hooks) |
| `tool` | `Tool` | Exposes a callable operation as an MCP tool |

New kinds CAN be added, but they require a new protocol in the kernel (rare). New PLUGINS within existing kinds require no kernel changes.

See [`concepts/plugins.md`](concepts/plugins.md) for the full plugin model.

## Three discovery paths

Kernel scans three locations at startup. All three use the same contract. Precedence when plugin IDs collide: **vault-local > user-global > entry points**.

1. **Python entry points** (`pyproject.toml` `[project.entry-points."kvault.plugins"]`) — for pip-installable plugins. The kernel's own bundled plugins use this path too; they are not special-cased.
2. **User-global** (`~/.config/kvault/plugins/<kind>/<name>/`) — machine-wide personal plugins.
3. **Vault-local** (`<vault>/kvault.plugins/<kind>/<name>/`) — per-vault handlers scoped to one vault.

## State lives in the vault

The kernel and its plugins are stateless code. All mutable state lives in the target vault:

- `memory/episodic/run-log.jsonl` — every tool invocation
- `memory/semantic/vault-capabilities.jsonl` — registry of installed + active plugins
- `memory/semantic/lineage.jsonl` — graph of who-cites-whom across vault entities
- `memory/semantic/proposals.jsonl` — consolidation output awaiting human review
- `memory/semantic/vectors.db` (if a vector store plugin is active) — embeddings
- `memory/rules/{proposed,active,retired}/<id>.md` — rule lifecycle

See [`concepts/state.md`](concepts/state.md).

## What's NOT in the kernel

Deliberately excluded:

- No scheduler / cron. Consolidation and rotation are manual triggers.
- No graph database (filesystem JSONL scales past vault sizes we care about).
- No vector database (delegated to a `vector_store` plugin if user wants one).
- No policy DSL. Policies are YAML frontmatter values, resolved by a `PolicyProvider` plugin.
- No auto-mutation of vault content. All proposed changes require human approval.
- No cross-vault shared state. Each vault is independent.

See [`adr/`](adr/) for the full reasoning behind each decision.
