# ADR 0003 — Plugin directories are organized by kind

Date: 2026-04-24
Status: Accepted

## Context

Where should a plugin's files physically live on disk? Two patterns are common in plugin-heavy systems:

**Flat by name**: `plugins/cohere_embedding/`, `plugins/ollama_embedding/`, `plugins/fts_only_retriever/`. Every plugin is a sibling at the same level. Over time the directory becomes a large flat list.

**Hierarchical by kind**: `plugins/embedding/cohere/`, `plugins/embedding/ollama/`, `plugins/retriever/fts_only/`. Plugins cluster with siblings of the same kind.

## Decision

Plugins are organized by kind. Canonical directory layout:

```
<plugin_root>/<kind>/<name>/
├── plugin.toml
├── handler.py
└── (optional: schema.json, README.md, ...)
```

This applies identically at all three discovery paths:

- Entry-point bundled: `src/kvault_mcp/plugins/<kind>/<name>/`
- User-global: `~/.config/kvault/plugins/<kind>/<name>/`
- Vault-local: `<vault>/kvault.plugins/<kind>/<name>/`

The plugin's **full ID** is `<kind>.<name>` (e.g., `embedding.ollama`, `retriever.qmd_wrapper`).

## Rationale

- **Add in one place.** If a user wants to add a new embedding provider, they create exactly one directory under `embedding/`. No naming convention to remember. No risk of mixing kinds.
- **Readable at a glance.** Listing `plugins/embedding/` shows every available embedding provider. No filtering needed.
- **Kind is structural, not cosmetic.** The kernel already treats kinds as first-class (one protocol per kind). The directory layout matching the conceptual model reduces cognitive load.
- **Cleaner IDs.** `embedding.ollama` is unambiguous. `cohere_embedding` collides with `cohere_reranker` alphabetically when listed.

## Consequences

- Tools that list plugins group by kind naturally via the directory structure.
- When the kernel introduces a new kind (rare), a new subdirectory appears. No migration needed for existing plugins.
- Plugin IDs include the kind as a prefix. This is slightly more verbose than flat names but is worth it for disambiguation and tooling simplicity.

## Alternatives considered

- Flat naming with kind embedded in the name: `cohere_embedding`, `qmd_retriever`. Rejected because the kind-in-name convention is unenforced and drifts over time.
- Kind in `plugin.toml` only, directory layout free: rejected because it lets kind-mixing happen in practice, making directory listings unhelpful.
