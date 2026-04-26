# ADR 0006: Three plugin discovery paths with strict precedence

**Status:** Accepted
**Date:** 2026-04-22

## Context

Users need multiple ways to install plugins:

- Packaged plugins from PyPI (for reusable, versioned components).
- Personal plugins shared across all vaults (user-global).
- Vault-specific plugins that travel with a vault (vault-local).

Each has legitimate use cases. A system that supports only one forces awkward workarounds.

## Decision

kvault-mcp discovers plugins from **three paths**, in this precedence (later overrides earlier):

1. **Entry points** — `importlib.metadata.entry_points(group="kvault.plugins")`. For pip-installed packages.
2. **User-global** — `~/.config/kvault/plugins/<kind>/<name>/`. For plugins shared across all vaults.
3. **Vault-local** — `<vault>/kvault.plugins/<kind>/<name>/`. For plugins specific to this vault.

If the same `kind/name` pair appears in multiple paths, the highest-precedence path wins. Lower-precedence duplicates are logged as `shadowed`.

## Rationale

- **Entry points** match standard Python packaging. Publishing a plugin to PyPI requires no special kvault-mcp machinery.
- **User-global** supports the common case: "I wrote a custom audit and want it in every vault I open."
- **Vault-local** supports experimentation and vault-specific logic without polluting the user's global space or publishing to PyPI.
- **Precedence vault > global > entry-point** matches mental model: "the vault in front of me is the most specific; published packages are the least specific."
- **Explicit shadowing** (not errors) lets users override a packaged plugin locally without uninstalling it.

## Consequences

### Positive

- Three distinct install ergonomics cover the common lifecycle: experiment locally → share globally → publish packaged.
- Vault portability: vault-local plugins travel with the vault directory.
- No coupling to a package registry — an offline user can still ship and share plugins via git.

### Negative

- Three paths to check at discovery time (cheap — both filesystem paths are bounded).
- Shadowing is a foot-gun: a vault-local plugin with a bug can shadow a working packaged plugin. Mitigation: `kvault.plugin.list` shows the path each plugin was loaded from, and shadows are logged.

## Alternatives considered

- **Entry points only.** Rejected: forces publishing to PyPI for every customization. Hostile to prototyping.
- **Entry points + vault-local only.** Rejected: forces users to duplicate a personal plugin into every vault. The user-global path is where "my personal toolkit" belongs.
- **Config-driven plugin paths.** Rejected: adds a chicken-and-egg problem — config lives in the vault, but the plugin discovery mechanism would need to read config before discovering.

## Related

- [`../concepts/plugins.md`](../concepts/plugins.md)
- [`0002-kernel-has-zero-plugins.md`](0002-kernel-has-zero-plugins.md)
