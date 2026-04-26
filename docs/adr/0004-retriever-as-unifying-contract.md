# ADR 0004 — Retriever is the unifying contract (composable OR monolithic)

Date: 2026-04-24
Status: Accepted

## Context

Two legitimate approaches to retrieval exist in the target ecosystem:

**Composable layers.** Retriever assembles its pipeline from smaller plugins (`embedding`, `vector_store`, `reranker`, FTS). The user configures each piece independently. Good for experimenting and swapping individual models.

**Monolithic backends.** A self-contained search system (e.g., qmd, or a future external MCP) does everything internally — embedding, storage, retrieval, reranking. The user plugs it in wholesale. Good for delegating to a specialized tool without re-implementing its pipeline.

A plugin system that forces one approach excludes the other. That's a rewrite hazard: switch pattern → rewrite the kernel and several plugins.

## Decision

Both approaches implement the same protocol: **`Retriever`**.

```python
class Retriever(Protocol):
    id: str
    def query(self, situation: str, k: int = 5) -> list[RetrievalResult]: ...
    def health(self) -> dict: ...
```

A retriever plugin may:

- **Compose** — ask the kernel's service registry for the active `embedding`, `vector_store`, `reranker` plugins and combine them. (Example: `retriever/hybrid_rrf/`.)
- **Monolithize** — ignore the layer plugins entirely and do its own thing, including wrapping an external tool or MCP server. (Example: `retriever/qmd_wrapper/`.)

Which retriever is active is a single config line: `[retrieval] active = "..."`.

## Rationale

- **One contract, many implementations.** Tools that need retrieval ask the kernel for "the active retriever" — they do not care how it works inside.
- **Clean migration paths.** Swap hybrid-rrf → qmd_wrapper → back → to a new lineage-walker retriever without touching anything except config.
- **Honest boundaries.** Composable pattern acknowledges that embedding + storage + reranking are separable concerns; monolithic pattern acknowledges that some tools (qmd) solve the whole problem and shouldn't be dismantled.

## Consequences

- Layer plugins (`embedding`, `vector_store`, `reranker`) may be loaded but unused when a monolithic retriever is active. That's fine — they stay dormant at negligible cost.
- A user running a monolithic retriever can optionally still activate layer plugins for other uses (e.g., a separate tool that needs embeddings for a different purpose). The kernel does not enforce "only one retriever kind used at a time."
- Layer plugins must tolerate operating in isolation. An `embedding` plugin is not required to participate in any particular retriever; it just needs to satisfy `EmbeddingProvider`.

## Alternatives considered

- Separate `SearchBackend` protocol for monolithic tools, `Retriever` for composable pipelines: rejected as unnecessary duplication. The caller always wants the same thing (`query() -> results`); internal implementation is the plugin's concern.
- Composable-only, with monolithic backends wrapped into fake sub-plugins: rejected as artificial. Forcing a monolithic backend to emit vectors through a virtual `vector_store` it internally owns is awkward and leaks abstraction.
