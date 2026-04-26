# ADR 0002 — The kernel has zero plugins baked in

Date: 2026-04-24
Status: Accepted

## Context

A common anti-pattern in plugin-heavy systems is for "core" plugins to be implemented inside the kernel and only "extensions" to go through the plugin mechanism. This creates two classes of components with different rules: core plugins can import kernel internals, rely on hidden globals, and couple to each other freely; external plugins cannot. Over time, the kernel becomes a monolith with a plugin loader bolted on.

We want to avoid that permanently.

## Decision

The kernel ships with **zero** plugins imported or referenced by kernel code.

Every plugin — including the audit suite, manifest builders, embedding providers, retrievers, hooks, rule sources, consolidators, policy providers — is discovered through the same three-path discovery mechanism:

1. Python entry points (`pyproject.toml` `[project.entry-points."kvault.plugins"]`)
2. User-global (`~/.config/kvault/plugins/<kind>/<name>/`)
3. Vault-local (`<vault>/kvault.plugins/<kind>/<name>/`)

Plugins that ship with the `kvault-mcp` package register via entry points in the package's own `pyproject.toml`. They are not imported directly by kernel code.

## Rationale

- **Single class of plugins.** Bundled and third-party plugins are indistinguishable at runtime. Same lifecycle, same contract, same coupling rules.
- **Delete-to-disable.** Removing a bundled plugin's directory causes its entry point to fail to resolve; kernel logs it and continues. No cascading breakage.
- **Testability.** Kernel tests don't need plugins loaded. Plugin tests don't need a running kernel except for integration tests.
- **Honesty of the contract.** If the kernel can't operate on a vault without core plugins, we'll find out fast — and so will users — rather than discovering a hidden dependency months in.

## Consequences

- The kernel alone does nothing useful. An install of just the kernel package + no plugins produces an MCP server that exposes no tools. The user MUST have at least one plugin of relevant kinds active to get anything done.
- Mitigation: the `kvault-mcp` distribution includes bundled plugins via entry points by default, so `uv tool install kvault-mcp` yields a working system out of the box.
- The `kvault.config.toml` file or defaults file shipped with the package decides which bundled plugins are active by default. Users override freely.

## Alternatives considered

- Kernel-imported core + plugins for extensions: rejected on the anti-pattern grounds described above.
- Plugin-per-package (one pip package per plugin): rejected as over-fragmented for v0.1. May revisit if the plugin catalog grows large enough to warrant independent release cycles.

## Enforcement

A `ruff` rule (CI-enforced) forbids any import from `kvault_mcp.plugins.*` inside `kvault_mcp.kernel.*` and `kvault_mcp.protocols.*`. Breaking this rule fails the build.
