# Vault

A vault is a directory. That's the whole definition. Anything beyond that is convention enforced by plugins, not by the kernel.

## Minimum viable vault

```
<vault>/
└── kvault.config.toml
```

With just that file, kvault-mcp can attach, discover plugins, resolve config, and serve MCP tools. Everything else (memory/, notes, manifests, rules) is created lazily by plugins as they operate.

## Conventional layout

A typical vault used with the shipped plugins looks like:

```
<vault>/
├── kvault.config.toml                # required
├── kvault.plugins/                   # optional: vault-local plugins
│   └── <kind>/<name>/
├── memory/                           # managed by plugins
│   ├── episodic/
│   ├── semantic/
│   ├── working/
│   ├── personal/
│   └── rules/
│       ├── proposed/
│       ├── active/
│       └── retired/
└── <user content>/                   # hubs, notes, sources — authored
```

None of these paths are hardcoded in the kernel. They are the output of plugin conventions. A different plugin set could produce a completely different layout.

## What the kernel needs

For the kernel to attach to a directory as a vault, exactly one thing must be true:

- `<vault>/kvault.config.toml` exists and parses as valid TOML.

If the file is missing, the kernel refuses to start. If it parses but is empty, the kernel starts with only defaults (no active plugins, no retrieval, no tools beyond built-ins).

## Vault identity

The vault's canonical identity is its **absolute path**. There is no vault UUID, no registry, no server-side index. If you move the directory, the vault moves. If you rename it, its identity changes.

Plugins that need a stable ID across moves (e.g., for correlation with external systems) should generate and persist one to `<vault>/memory/semantic/vault-identity.json` on first run.

## Multi-vault operation

A single kernel instance serves one vault at a time. To serve multiple vaults, run multiple MCP server processes — one per vault. They share nothing.

This is a deliberate simplification. Plugins don't need to think about multi-tenancy; state paths don't need vault prefixes; configs don't collide. If an agent needs to work across vaults, it connects to multiple MCP servers, one per vault.

## Vault portability

Because all meaningful state lives in the vault (see [`state.md`](state.md)), a vault is portable:

- Copy the directory to another machine → everything works if that machine has a compatible kvault-mcp install.
- Put it in git → history is preserved; derived state (run-log, manifests) can be gitignored or committed per policy.
- Back it up → one directory, one backup.

The only external dependency is the plugins referenced in config. If a vault config activates `embedding.ollama` and the new machine has no Ollama running, that plugin fails health; other plugins continue. The vault is not corrupted — it's simply missing a dependency.

## Vault-local plugins

A vault can ship its own plugins under `kvault.plugins/<kind>/<name>/`. These take precedence over user-global and entry-point-installed plugins of the same `kind/name` (see [`plugins.md`](plugins.md)).

This lets a vault carry its own custom retriever, audit, or embedding provider — for a domain-specific workflow that isn't worth publishing as a package. Moving the vault moves the plugins with it.

## What a vault is not

- Not a database. It's a directory. Plugins may create SQLite files inside it, but the vault itself is not queryable as a unit.
- Not a service. The vault is passive; the kernel + plugins are the active component.
- Not opinionated about content. The kernel doesn't care whether the vault holds markdown notes, code, or binary blobs. Plugins impose structure; the kernel does not.
