# Retrieval

How kvault-mcp answers *"show me relevant knowledge for this situation"* — and how users swap any piece of that pipeline without rewrites.

## Two patterns, one contract

Every retriever implements the same protocol:

```python
class Retriever(Protocol):
    id: str
    def query(self, situation: str, k: int = 5) -> list[RetrievalResult]: ...
    def health(self) -> dict: ...
```

Retrievers come in two flavors, distinguished only by what they use internally:

### Pattern A — Composable

The retriever asks the kernel's service registry for the active `embedding`, `vector_store`, and (optional) `reranker` plugins. It combines their outputs.

Example: `retriever/hybrid_rrf/` runs FTS5 + vector search in parallel, blends results via Reciprocal Rank Fusion, optionally reranks.

```
query → hybrid_rrf ──┬─► embedding (active) ─► vector_store (active) ─┐
                     │                                                 │
                     └─► FTS5 index ──────────────────────────────────┤
                                                                       │
                                        ┌── reranker (if any) ◄────────┘
                                        │
                                        └── final results
```

Swap the embedding model: change `kvault.config.toml`, rebuild vectors, restart. Retriever doesn't know anything changed.

### Pattern B — Monolithic

The retriever is a complete search system on its own. It does not use `embedding` or `vector_store` plugins. It wraps an external tool (e.g., qmd's MCP server) or has its own internal pipeline.

Example: `retriever/qmd_wrapper/` proxies queries to a separately-installed qmd MCP server. qmd handles embedding, storage, reranking internally.

```
query → qmd_wrapper ─► (external qmd MCP server) ─► results
```

Swapping TO qmd: install qmd, install kvault's qmd_wrapper plugin (or drop in `<vault>/kvault.plugins/retriever/qmd_wrapper/`), set `[retrieval] active = "qmd_wrapper"` in config. Other plugins (embedding, vector_store) stay loaded but idle.

## Active retriever selection

`kvault.config.toml` has one line that decides which retriever is active:

```toml
[retrieval]
active = "hybrid_rrf"   # or "qmd_wrapper", "fts_only", or any installed retriever
```

All MCP tools that need retrieval (`vault.advisory.query`, `vault.consolidate`, etc.) ask the kernel for *"the active retriever"*. They get back one object conforming to the `Retriever` protocol. They do not know which backend is behind it.

## Why this works for extensibility

User wants to try a new retrieval approach (say, a graph-walk retriever based on the lineage manifest):

1. Create `<vault>/kvault.plugins/retriever/lineage_walker/` with `plugin.toml` + `handler.py`.
2. Implement `Retriever.query()` — free to use any plugins or no plugins.
3. Restart MCP server.
4. Set `[retrieval] active = "lineage_walker"` in config.
5. Done. No code in the kernel changes. No other retriever changes. No audit, manifest builder, rule source, etc. knows anything happened.

If the new retriever beats the current one, keep it. If not, change config back. A/B is a config edit.

## Embedding models and re-embedding

The embedding model is config, not code. Plugins never hardcode dimensions or model names.

```toml
[plugins.embedding.ollama]
active = true
endpoint = "http://localhost:11434"
model = "mxbai-embed-large:latest"
dimensions = 1024
```

Switching models requires re-embedding (stored vectors are bound to a specific model + dimensions).

### Versioned collections

Each time embeddings are built, the vector_store creates a new **collection** tagged with metadata:

```json
{
  "collection_id": "mxbai-embed-large_1024_2026-04-24",
  "model": "mxbai-embed-large:latest",
  "dimensions": 1024,
  "created_at": "2026-04-24T...",
  "document_count": 420,
  "active": true
}
```

Only the active collection answers queries. Old collections are retained (for rollback + A/B) until explicitly pruned.

### Changing models — the flow

1. Pull the new model (e.g., `ollama pull embeddinggemma`).
2. Edit `kvault.config.toml`: update `model`, `dimensions`.
3. Restart MCP server (picks up new config).
4. Call `vault.embeddings.rebuild()` — creates a new collection with the new model.
5. New collection becomes active automatically.
6. Verify with a few queries.
7. Optionally `vault.embeddings.prune(keep_last=2)` to drop old collections.

No data migration scripts. No code changes. No cross-plugin coordination. Each plugin reads its config and does its job.

## Failure modes, made explicit

- **No embedding plugin active** → any retriever that requires vectors (like `hybrid_rrf`) will degrade to its FTS-only path or fail cleanly with a health check. Composable retrievers declare which plugins they need; if missing, their `health()` reports unreachable and config validation flags it at startup.
- **Ollama unreachable** → embedding plugin's health check reports it; retriever falls back to FTS if it can, or errors loudly with a clear message.
- **Vector store corrupted** → `vault.embeddings.status()` surfaces it; `vault.embeddings.rebuild()` recovers.

All failures surface through standard health endpoints. Nothing silent.

## Related docs

- [`concepts/plugins.md`](plugins.md) — the plugin model in general
- [`concepts/service-registry.md`](service-registry.md) — how retrievers find other plugins
- [`adr/0004-retriever-as-unifying-contract.md`](../adr/0004-retriever-as-unifying-contract.md) — why both patterns share one protocol
