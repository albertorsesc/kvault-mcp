# Plugins

Everything useful in kvault-mcp is a plugin. This page describes what a plugin is, how it's discovered, what it must declare, and how it interacts with other plugins.

## A plugin is a directory

```
<plugin_root>/<kind>/<name>/
├── plugin.toml       # manifest — required
├── handler.py        # the protocol implementation
├── schema.json       # optional JSON Schema for the plugin's config
└── README.md         # optional, recommended
```

The `<kind>/<name>/` hierarchy lets every plugin of a given kind sit next to its siblings. For example:

```
embedding/
├── ollama/
├── openai_compatible/
└── cohere/            # added later by a user, no kernel change

retriever/
├── fts_only/
├── hybrid_rrf/
└── qmd_wrapper/       # monolithic backend wrapping an external MCP
```

## `plugin.toml` — the manifest

Every plugin declares itself here. Example:

```toml
id = "ollama"                       # unique within kind; dotted-path = "embedding.ollama"
kind = "embedding"                  # one of the kernel's declared kinds
version = "0.1.0"                   # semver for the plugin
protocol_version = "1.0"            # protocol version this plugin targets
module = "handler"                  # Python file to import (relative)
entrypoint = "OllamaEmbedding"      # class in that module

# Optional wiring hints
consumes_events = []                # event types this plugin subscribes to
emits_events = []                   # event types this plugin publishes
provides = ["embedding_provider"]   # service-registry tags

# Optional config
config_schema = "schema.json"       # JSON Schema for this plugin's config block

# Optional install requirements (kernel will advise user; never auto-installs)
install_required = []               # e.g. ["sentence-transformers>=3.0"]

description = "Ollama HTTP embedding provider"
author = "..."
license = "MIT"
```

The kernel validates every manifest against a schema at load time. Bad manifest → plugin skipped with a clear log line. Never crashes the kernel.

## `handler.py` — the implementation

The `entrypoint` must be a class that implements the protocol declared for the plugin's `kind`. The kernel imports the module and instantiates the class, passing resolved config.

Example for an `embedding` plugin:

```python
from kvault_mcp.protocols import EmbeddingProvider

class OllamaEmbedding(EmbeddingProvider):
    id = "embedding.ollama"

    def __init__(self, config: dict):
        self.endpoint = config["endpoint"]
        self.model = config["model"]
        self.dimensions = config["dimensions"]

    def embed(self, texts: list[str]) -> list[list[float]]:
        # HTTP call to Ollama; return N vectors of self.dimensions floats
        ...

    def health(self) -> dict:
        return {"status": "ok" if self._reachable() else "unreachable",
                "model": self.model}
```

The protocol methods are the ONLY thing the plugin must implement. Everything else (lifecycle, config, eventing) is handled by the kernel.

## Three discovery paths

At startup, the kernel scans three locations. All three use the same manifest contract. Plugins loaded here are indistinguishable at runtime.

1. **Python entry points** — installed pip packages declare in their `pyproject.toml`:
   ```toml
   [project.entry-points."kvault.plugins"]
   ollama_embedding = "kvault_mcp.plugins.embedding.ollama:manifest"
   ```
   The kernel uses `importlib.metadata.entry_points(group="kvault.plugins")` to find them. Bundled plugins ship with kvault-mcp itself via this path — they are not special.

2. **User-global** — `~/.config/kvault/plugins/<kind>/<name>/`. Machine-scoped; available to every vault.

3. **Vault-local** — `<vault>/kvault.plugins/<kind>/<name>/`. Scoped to one vault. Useful for vault-specific experiments or proprietary plugins.

**Precedence on ID collision**: vault-local > user-global > entry points. You can override a bundled plugin by dropping a same-ID one locally.

## Kinds currently defined by the kernel

| Kind | What the plugin does |
|---|---|
| `embedding` | Text → vector |
| `vector_store` | Persist and query vectors |
| `reranker` | Reorder retrieved candidates |
| `retriever` | Assemble a query pipeline (composable or monolithic) |
| `manifest` | Produce a durable state file |
| `audit` | Inspect vault, emit findings |
| `rule_source` | Capture rule candidates |
| `consolidator` | Surface patterns as proposals |
| `policy_provider` | Resolve a named policy |
| `hook` | Runtime-invoked lifecycle handler |
| `tool` | Exposed as an MCP tool |

New kinds require a new protocol in `src/kvault_mcp/protocols/`. Rare. Most extension happens within existing kinds.

## Lifecycle

1. **Discovery** — kernel scans the three paths, loads manifests.
2. **Validation** — manifest schema + protocol_version check. Incompatible plugins are skipped with a warning.
3. **Config resolution** — kernel merges config (`kvault.config.toml` + env + runtime) and validates against the plugin's `schema.json` if present.
4. **Instantiation** — kernel imports module, constructs `entrypoint(config)`.
5. **Health check** — kernel calls `plugin.health()`. Failures log and deactivate the plugin without crashing others.
6. **Registration** — plugin enters the service registry under its `provides` tags, subscribes to declared events.
7. **Operation** — plugin receives calls (sync via registry lookups) or events (async via bus).
8. **Shutdown** — kernel calls `plugin.close()` if defined.

## The golden rule

A plugin may import:

- `kvault_mcp.protocols.*` (the contracts it implements)
- Its own files
- Standard library + its declared third-party deps

A plugin must not import:

- Any other plugin's module directly.
- Any plugin-specific kernel helper by path (only the public `kernel` API is allowed).

Enforced by `ruff` rules in the kernel's CI and by the design of the kernel's public surface. This is what makes "no component knows about another" real.

See [`concepts/service-registry.md`](service-registry.md) and [`concepts/events.md`](events.md) for how plugins coordinate without direct references.
