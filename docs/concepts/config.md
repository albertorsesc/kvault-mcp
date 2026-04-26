# Configuration

Configuration is layered, declarative, and per-vault. The kernel reads one TOML file at the vault root; plugins declare what they accept via JSON Schema.

## Layers

Config resolves in precedence order (later overrides earlier):

1. **Plugin defaults** — values declared in the plugin's `schema.json` `default` fields.
2. **Vault config** — `<vault>/kvault.config.toml`.
3. **Environment variables** — `KVAULT_<PLUGIN_ID>_<KEY>` (uppercased, underscored).
4. **Runtime overrides** — passed via MCP tool arguments (rare; used for experiments).

No CLI flags, no per-user global config overriding vault config. The vault is the unit of configuration.

## The vault config file

`<vault>/kvault.config.toml`:

```toml
# Global kernel settings
[kernel]
log_level = "info"                       # debug | info | warn | error
state_root = "memory"                    # relative to vault root

# Active retriever (chosen among registered retriever plugins)
[retrieval]
active = "hybrid_rrf"

# Per-plugin config, addressed as [plugins.<kind>.<name>]
[plugins.embedding.ollama]
active = true
endpoint = "http://localhost:11434"
model = "mxbai-embed-large:latest"
dimensions = 1024
normalize = true

[plugins.vector_store.sqlite_vec]
active = true
path = "memory/semantic/vectors.db"

[plugins.retriever.hybrid_rrf]
active = true
k_fts = 20
k_vec = 20
rrf_k = 60

[plugins.retriever.fts_only]
active = false
```

### Addressing

- `[kernel]` and `[retrieval]` are fixed sections owned by the kernel.
- `[plugins.<kind>.<name>]` matches a plugin at `<plugin_root>/<kind>/<name>/`.
- `active = true|false` is the universal toggle. Inactive plugins are still discovered and validated but not instantiated.
- Everything else under `[plugins.<kind>.<name>]` is passed opaquely to that plugin after schema validation.

## Per-plugin schemas

Every plugin ships a `schema.json` (JSON Schema draft 2020-12). Example:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "active":     { "type": "boolean", "default": false },
    "endpoint":   { "type": "string",  "format": "uri", "default": "http://localhost:11434" },
    "model":      { "type": "string" },
    "dimensions": { "type": "integer", "minimum": 1 },
    "normalize":  { "type": "boolean", "default": true }
  },
  "required": ["model", "dimensions"]
}
```

Validation happens at kernel startup. A plugin whose config fails schema validation is **not instantiated** and the failure is logged as a structured finding. Other plugins continue unaffected.

## Environment variables

Any plugin config key can be overridden via env var:

```
KVAULT_EMBEDDING_OLLAMA_ENDPOINT=http://remote:11434
KVAULT_RETRIEVER_HYBRID_RRF_K_FTS=40
```

Naming: `KVAULT_<KIND>_<NAME>_<KEY>`, all uppercase, dots and hyphens become underscores.

Env vars are the documented channel for **secrets**. API keys, tokens, and anything sensitive go here, never into `kvault.config.toml`.

## Viewing resolved config

```python
kernel.config("embedding.ollama")
# returns the fully-resolved dict after defaults + TOML + env merge
```

Plugins call this in their constructor; the kernel never injects config automatically — plugins pull what they need by plugin ID.

## Changing config

Config is reloaded on kernel startup. There is **no hot-reload**. Changing `kvault.config.toml` requires restarting the MCP server. This is intentional: config changes can reshape retrieval, rotate embedding models, or swap active plugins — the audit trail expects a clean boundary.

## What config is not

- Not a plugin registry — plugins are discovered independently (see [`plugins.md`](plugins.md)).
- Not a secret store — secrets live in env vars or OS keychains.
- Not per-environment — each vault has one config; different environments get different vaults.
