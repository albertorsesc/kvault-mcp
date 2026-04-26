# ADR 0009: FastMCP 3 with a custom Provider for plugin-sourced tools

**Status:** Accepted
**Date:** 2026-04-24

## Context

kvault-mcp needs to expose an MCP server over stdio. The tools it exposes are not known at import time — they come from discovered plugins. The MCP surface must therefore support:

- Tools registered imperatively after server construction.
- Schema inference from plugin-declared handlers (or explicit schemas in `plugin.toml`).
- `notifications/tools/list_changed` when plugins load or unload at runtime.

Three viable implementations were evaluated:

1. **Official `mcp` SDK, low-level `Server`** — decorator-based handlers (`@server.list_tools`, `@server.call_tool`). Dynamic registration requires a hand-rolled `ToolRegistry` + manual notification emission. ~150 lines of boilerplate the kernel owns.
2. **Official `mcp` SDK, high-level `FastMCP`** — decorator-only; tools bind at decoration time. Dynamic registration is awkward (`add_tool` exists but no dynamic list source).
3. **Standalone `fastmcp` 3.x** (Jeremiah Lowin / Prefect) — ships a `Provider` abstraction literally designed for "pull tools from a registry at runtime." `FileSystemProvider`, `DatabaseProvider`, and custom subclasses are supported. `add_provider()` for runtime composition. Wraps the official SDK's wire protocol.

## Decision

Use **standalone `fastmcp` 3.x** and implement a custom `Provider` that sources tools from kvault's kernel (`KernelCore.loaded_plugins()`).

## Rationale

- **Architectural fit is exact.** Our discovery pipeline produces a list of loaded plugins with tool metadata; FastMCP's Provider contract is `_list_tools() -> Sequence[Tool]` + `_get_tool(name) -> Tool | None`. Translation is ~30 lines.
- **Kernel stays small.** FastMCP owns schema serialization, `tools/list_changed` notifications, transport negotiation, progress / error protocol. We don't maintain parallel implementations.
- **Wire protocol parity.** `fastmcp` 3 wraps the official `mcp` SDK internally. Any MCP client that speaks to an official-SDK server speaks to ours identically.
- **FOSS + heavy production use.** MIT license; reportedly powers ~70% of MCP servers in the wild as of 2026. Active maintenance by Prefect.
- **Low lock-in.** If we ever need to swap back to the official SDK's low-level `Server`, the kernel's plugin contract is unchanged — only `server.py` is rewritten. Plugins don't depend on FastMCP.

## Consequences

### Positive

- Kernel-side MCP code is minimal: one Provider subclass, one `FastMCP(...)` construction, one `mcp.run(...)` call.
- Hot-reload (re-discovering plugins at runtime) is a matter of telling the Provider its source changed; FastMCP re-queries on every list request by default.
- Official-SDK feature gaps (dynamic tool sourcing, schema inference, progressive disclosure) are already solved upstream.

### Negative

- One additional community dependency. Mitigation: pinned `fastmcp>=3.2,<4` (SemVer boundary). Migration to the official SDK's low-level Server remains possible — the kernel's plugin contract does not leak FastMCP types.
- Slight risk of divergence from the official MCP spec if FastMCP adds non-standard extensions. Mitigation: restrict usage to Provider + core `FastMCP` class; avoid experimental transforms (`CodeMode`, etc.) in the kernel.

## Alternatives considered

- **Official `mcp` lowlevel Server.** Rejected for the volume of hand-rolled dynamic-registration code we'd maintain. Usable but higher ongoing cost.
- **Official `mcp` FastMCP (high-level).** Rejected: decorator-first API is a poor fit for plugin-sourced tools whose identity and schema are only known after kernel discovery.
- **Roll our own MCP transport.** Rejected. Off-topic from the project's scope.

## Related

- [`../development/external-apis.md`](../development/external-apis.md) §6
- [`../concepts/kernel.md`](../concepts/kernel.md) — "MCP wiring" paragraph
