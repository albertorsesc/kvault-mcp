# Changelog

All notable changes to kvault-mcp are documented here. This project follows [Semantic Versioning](https://semver.org/) and the format of [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added — Phase D (rules lifecycle + injection)
- `RuleStore` + `RuleInjector` Protocols with matching `Base*` scaffolding.
- `plugins/rules/store/markdown/` — file-backed rule store over
  `memory/rules/{proposed,active,retired}/` with frontmatter-driven
  status transitions. Emits `vault.rule.{proposed,activated,retired}`
  events.
- `plugins/rules/injector/markdown_markers/` — renders active rules
  between `<!-- kvault:rules:start --> / <!-- kvault:rules:end -->`
  markers in a configurable target file. Auto-refreshes on rule
  state changes via the event bus. Idempotent; content outside the
  markers is preserved.

### Added — Phase C (manifests + audits)
- Shared `vault/` primitives: `extract_wikilinks`, `parse_frontmatter`,
  `iter_markdown_files`, `atomic_write_jsonl`, `iter_jsonl`.
- `plugins/manifest_builder/{capabilities,frameworks,lineage}/` —
  JSONL manifest builders that replace the vault's hand-written
  `scripts/build-*.sh` equivalents.
- `plugins/audit/{schemas,broken_wikilinks,lineage_dangling}/` —
  read-only validators producing structured `Finding` records.
- TempVault TOML writer now emits inline tables for dict-of-scalars so
  config keys containing dots (file paths) round-trip correctly.
- Discovery walks plugin directories recursively; `plugin.toml`'s
  `kind` and `id` are authoritative, matching the entry-point path.

### Added — Phase B (retrieval stack)
- Bundled plugins: `embedding/ollama`, `vector_store/sqlite_vec`,
  `text_index/fts5`, `retriever/fts_only`, `retriever/hybrid_rrf`.
- `RetrievalResult.to_dict()` for MCP serialization.
- `BaseRetriever` / `BaseTextIndex` ship shared `tool_search` /
  `tool_rebuild` MCP adapters.
- `BaseEmbeddingProvider` ships Template Method batching; concrete
  providers override `_embed_batch` only.

### Added — Phase A (foundation)
- `core/` kernel: `ServiceRegistry`, `EventBus`, `ConfigResolver`,
  `StatePathResolver`, `PluginLifecycle`, `KernelCore`.
- `kinds/` subsystem: one module per kind, each colocating Protocol +
  Base + kind-specific dataclasses. `register_provider_type()` enables
  third-party kinds.
- Three-path plugin discovery (entry points / user-global / vault-local)
  with precedence + shadow-detail logging.
- `TempVault` test harness.
- FastMCP 3.x integration via custom `KvaultPluginProvider`.
- Post-wiring health refresh: plugins whose health depends on other
  plugins reflect their fully-wired state in the public summary.
- OSS hygiene: `CONTRIBUTING.md`, `CHANGELOG.md`, `SECURITY.md`,
  `CODE_OF_CONDUCT.md`, GitHub Actions CI.

### Security
- Hardened `state_path(category, name)` — rejects absolute paths and
  `..` traversal via `PathEscape`. Plugins cannot escape their
  assigned state category.
- Plugin manifest parser tolerates malformed `plugin.toml` — one
  broken plugin no longer takes down the kernel.
- Secret-redaction heuristic uses exact + suffix match (`api_key`,
  `token`, `secret`, `password`) rather than substring. Eliminates
  false positives like `secret_path`.
- `check_same_thread=False` on all SQLite connections so MCP dispatch
  from another thread doesn't crash reads.

### Stats
- 13 bundled plugins across 8 kinds.
- 95 tests (regression + adversarial + integration). Ruff clean. CI
  builds wheel on every push.
