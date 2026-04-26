# ADR 0005: State lives in the vault, not in the kernel

**Status:** Accepted
**Date:** 2026-04-22

## Context

kvault-mcp is stateful — it stores runs, manifests, proposals, rules, embeddings. That state could live in:

1. **Kernel-local directory** — e.g., `~/.local/share/kvault/` — shared across all vaults the kernel serves.
2. **Inside each vault** — `<vault>/memory/` — scoped to the vault it belongs to.

The choice affects portability, multi-vault operation, and the blast radius of reinstalls.

## Decision

**All mutable state lives inside the target vault.** The kernel and plugins are stateless code. Deleting the kvault-mcp install and reinstalling loses zero vault data.

## Rationale

- **Multi-vault.** One kernel serves N vaults, each with its own state. No collision, no tenancy logic, no shared-state corruption.
- **Portability.** A vault is a directory. Moving it to another machine moves its run history, manifests, embeddings, rules — everything. Users think in vaults, not in "kvault installs."
- **Reinstalls are safe.** Upgrading the package, reinstalling the kernel, or wiping `~/.local/share/` never loses user data.
- **Debuggability.** State is on disk inside the vault the user already has open. `grep`, `jq`, text editors all work.
- **Git-native.** Vault state can be committed or gitignored per user policy. The kernel doesn't care.

## Consequences

### Positive

- Clean identity model: the vault directory *is* the unit of state.
- No shared database, no migration between kernel versions (plugins manage their own schemas).
- Debug info is co-located with the content it describes.

### Negative

- Each vault carries its own indexes. Embeddings for identical content across two vaults are stored twice.
- No cross-vault queries without running multiple kernels and federating client-side.
- Vault sizes grow — users must manage retention (plugins provide rotation; users pick policies).

## Alternatives considered

- **Kernel-local state with vault ID prefixes.** Rejected: moving a vault to another machine loses its history. Sync'ing the kernel dir separately defeats the "one directory is the vault" mental model.
- **Hybrid (small state in kernel, large state in vault).** Rejected: the split point becomes a design question every plugin has to answer. Uniform rule is simpler.

## Related

- [`../concepts/state.md`](../concepts/state.md)
- [`../concepts/vault.md`](../concepts/vault.md)
