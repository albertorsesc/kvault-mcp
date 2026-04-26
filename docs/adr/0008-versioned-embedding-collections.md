# ADR 0008: Versioned embedding collections for model switching

**Status:** Accepted
**Date:** 2026-04-22

## Context

Embedding models evolve. A user starts with `mxbai-embed-large` (1024 dims), later switches to `gemma-embed-4` (768 dims), later tries an experimental model. Each switch requires re-embedding the corpus, which takes hours. During the transition, the system must:

- Continue serving queries without downtime.
- Allow fallback to the previous model if the new one underperforms.
- Not mix vectors from different models in the same index (dimensions differ, semantic space differs).

Naive designs conflate "the vector store" with "the model," forcing destructive migrations.

## Decision

The vector store holds **multiple named collections**, each tagged with the embedding model that produced it. A `collection` = `(model_id, dimensions, created_at, status)`. The active collection is chosen per-query by the retriever via config.

Collection naming: `<provider>__<model>__<version>__<YYYYMMDD>`.

Example metadata row (in `memory/semantic/vectors.db`):

```
collection_id: ollama__mxbai-embed-large__v1__20260412
provider: ollama
model: mxbai-embed-large
dimensions: 1024
created_at: 2026-04-12T10:00:00Z
vector_count: 4821
status: active
```

Config selects the active collection:

```toml
[retrieval]
active_collection = "ollama__mxbai-embed-large__v1__20260412"
```

Re-embedding creates a new collection alongside the old one. The old one becomes `status: retired` once the new one is validated. Retired collections can be pruned via `kvault.embeddings.prune`.

## Rationale

- **Zero-downtime model switching.** Build the new collection in the background; flip `active_collection` atomically when done.
- **Rollback is free.** If the new model underperforms, flip config back. No data loss.
- **A/B evaluation.** A retriever can query two collections and compare results before committing to the switch.
- **Provenance is explicit.** Every vector is traceable to the exact model version that produced it. No silent semantic drift.
- **No premature migration.** Users re-embed on their schedule, not on package upgrades.

## Consequences

### Positive

- Switching embedding models is a config change, not a data migration.
- Storage grows during transitions (both old and new collections coexist) but is bounded by explicit pruning.
- Audit and observability are straightforward — every run-log entry can record which collection served it.

### Negative

- Disk usage during transitions can double. Mitigation: users prune retired collections when they're confident in the new one.
- More state to track per vault. Mitigation: the plugin that manages collections ships with list/prune/compare tools; users never hand-edit the metadata.
- Retriever plugins must be collection-aware. Mitigation: retrievers receive the active collection ID from config; they don't discover it.

## Alternatives considered

- **Single collection, destructive re-embed.** Rejected: no rollback, downtime during re-embed, high risk.
- **One collection per model with no versioning.** Rejected: re-embedding the same model (e.g., after a data cleanup) should produce a new collection, not overwrite. Date-stamped versioning supports this.
- **Collection per content type (hubs, notes, sources).** Rejected: orthogonal concern; handled by per-collection filters, not by collection identity.

## Related

- [`../concepts/retrieval.md`](../concepts/retrieval.md)
- [`../concepts/state.md`](../concepts/state.md)
