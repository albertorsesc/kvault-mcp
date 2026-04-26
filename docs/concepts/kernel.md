# Kernel

The kernel is the only code that runs regardless of which plugins are installed. It does a small, fixed set of jobs; everything else is a plugin's concern.

## What the kernel does

1. **Discovery** — at startup, scans three paths ([`plugins.md`](plugins.md)) for `plugin.toml` manifests.
2. **Validation** — checks each manifest against the manifest schema; checks `protocol_version` compatibility; skips and logs incompatible plugins without crashing.
3. **Config loading** — loads and merges config from defaults → user-global → vault-local → env vars → runtime overrides. Validates each plugin's config block against that plugin's JSON Schema if declared.
4. **Service registry** — keeps the set of instantiated plugins organized by protocol. Callers ask for "the active plugin implementing X" or "all plugins implementing X."
5. **Event bus** — publishes and dispatches events. Plugins subscribe declaratively via `plugin.toml`.
6. **Lifecycle** — instantiation, health checks, graceful shutdown, hot reload (reloads a single plugin without restarting the whole server).
7. **MCP wiring** — discovers plugins of kind `tool`, registers them as MCP tools with the MCP client; exposes resources for committed state (manifests, run log).
8. **State path resolution** — standardizes where per-vault state lives (see [`state.md`](state.md)). Plugins call `kernel.state_path(category, name)` instead of hardcoding paths.
9. **Logging + run-log emission** — emits structured events to the target vault's `memory/episodic/run-log.jsonl` so every tool call is traceable.

## What the kernel does NOT do

- **No audits.** Audits are plugins.
- **No manifest building.** Manifest builders are plugins.
- **No rule enforcement.** Rules are data; audits and hooks enforce them.
- **No retrieval.** Retrievers are plugins.
- **No consolidation.** Consolidators are plugins.
- **No scheduling.** The kernel never runs anything on a timer. Triggers come from MCP tool calls or external events.
- **No cross-plugin calls.** The kernel never calls one plugin from inside another plugin's code path. Coordination happens through the service registry (sync lookup) or event bus (async pub/sub).

## Stateless

The kernel itself holds no persistent state. The in-memory registry + event subscriptions are rebuilt from disk on every boot. If the kernel restarts, no information is lost — everything that mattered was written to the target vault's `memory/`.

## API exposed to plugins

Plugins see a small public surface. Anything not in this list is internal and may change between versions.

```python
from kvault_mcp.kernel import Kernel

kernel.get_active(protocol: type[P]) -> P | None
kernel.get_all(protocol: type[P]) -> list[P]
kernel.publish(event_type: str, payload: dict) -> None
kernel.state_path(category: str, name: str) -> Path
kernel.config(plugin_id: str) -> dict
kernel.logger(plugin_id: str) -> Logger
```

Plugins never import `kvault_mcp.kernel.internal.*`. If they try, CI fails.

## Why this scope

The kernel's job is to make plugins possible, not to do the work. Every responsibility added to the kernel is one that can't be swapped, extended, or replaced by a user. Keeping the kernel small is how we keep the system extensible.
