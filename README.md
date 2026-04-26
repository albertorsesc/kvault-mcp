# kvault-mcp

A plugin-first MCP server for operating on knowledge vaults — the kernel that turns a directory of markdown notes into a living, queryable, self-maintaining system.

**Status:** alpha (`0.1.0`). Runs end-to-end against real vaults today — indexing, search, manifest building, structural audits, and a proposed→active→retired rule lifecycle that auto-injects into `CLAUDE.md`. APIs may still shift before `1.0`.

## What this is

- An **MCP server** — exposes tools for any AI agent (Claude Code, Cursor, Claude Desktop, …) to operate on a vault over stdio.
- **Plugin-first** — the kernel does discovery, lifecycle, and coordination. Everything else is a plugin: retrievers, embedding providers, vector stores, text indexes, manifest builders, audits, rule stores, rule injectors.
- **Vault-first** — all state lives inside the target vault. Reinstall the package without losing anything. One kernel serves one vault at a time; run many processes for many vaults.
- **SOLID-bounded** — each plugin has one job (SRP), new kinds plug in without editing the kernel (OCP), Protocols give structural typing (LSP/ISP), and every plugin talks to the kernel abstraction only (DIP). Zero plugin-to-plugin imports.

## Bundled plugins

Ship via the same entry-point mechanism third-party plugins use — no special-casing.

| Kind | Name | Purpose |
|---|---|---|
| `embedding` | `ollama` | Local HTTP embeddings (stdlib client, batching) |
| `vector_store` | `sqlite_vec` | Per-collection `vec0` tables, versioned for model switches |
| `text_index` | `fts5` | SQLite FTS5 with BM25 + snippets + rebuild |
| `retriever` | `fts_only` | Keyword-only retrieval via the active TextIndex |
| `retriever` | `hybrid_rrf` | Hybrid FTS + vector fusion via Reciprocal Rank Fusion |
| `manifest_builder` | `capabilities` | One row per discovered plugin → `vault-capabilities.jsonl` |
| `manifest_builder` | `frameworks` | Framework notes with frontmatter → `frameworks.jsonl` |
| `manifest_builder` | `lineage` | All `[[wikilink]]` edges → `lineage.jsonl` |
| `audit` | `schemas` | Validates every JSONL against its JSON Schema |
| `audit` | `broken_wikilinks` | Finds `[[links]]` with no target note |
| `audit` | `lineage_dangling` | Flags lineage edges pointing at unknown frameworks |
| `rule_store` | `markdown` | File-backed rule lifecycle under `memory/rules/` |
| `rule_injector` | `markdown_markers` | Renders active rules into `CLAUDE.md` between HTML markers |

## Install

```bash
uv tool install kvault-mcp
# or inside a project:
uv add kvault-mcp
```

Requires Python 3.13+ with SQLite loadable-extension support (Homebrew Python works; macOS system Python does not — see [`docs/development/external-apis.md`](docs/development/external-apis.md) §2).

## Run against a vault

```bash
kvault-mcp --vault /path/to/vault
# or
KVAULT_VAULT=/path/to/vault kvault-mcp
```

Register with Claude Code:

```bash
claude mcp add kvault --scope user \
  -e KVAULT_VAULT=/path/to/vault \
  -- kvault-mcp
```

## Minimal vault config

```toml
# <vault>/kvault.config.toml
[plugins.text_index.fts5]
active = true
roots = ["."]
extensions = [".md"]

[plugins.retriever.fts_only]
active = true
```

That's the floor. Every other plugin is opt-in via `[plugins.<kind>.<name>]` blocks. See [`docs/concepts/config.md`](docs/concepts/config.md).

## Write your own plugin

Drop a directory into any of the three discovery paths:

- `<vault>/kvault.plugins/<anywhere>/` — vault-scoped
- `~/.config/kvault/plugins/<anywhere>/` — user-wide
- Entry point group `kvault.plugins` in any pip-installed package

Minimum: `plugin.toml` + `handler.py`. See [`docs/development/adding-a-plugin.md`](docs/development/adding-a-plugin.md).

## Documentation

| Where | What |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Meta architecture — kernel, plugins, events, registry, state |
| [`docs/concepts/`](docs/concepts/) | One file per core concept: kernel, plugins, retrieval, rules, manifests, audits, events, service registry, state, config, consolidation, vault |
| [`docs/development/`](docs/development/) | Adding a plugin · testing · external API reference |
| [`docs/adr/`](docs/adr/) | Architecture Decision Records (9 and counting) |
| [`CHANGELOG.md`](CHANGELOG.md) | What's in each version |
| [`SECURITY.md`](SECURITY.md) | Threat model + how to report issues |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to contribute |

## License

MIT. See [LICENSE](./LICENSE).

## Author

Alberto Rosas (<https://github.com/albertorsesc>).
