# ADR 0001 — Python + uv + single package

Date: 2026-04-24
Status: Accepted

## Context

kvault-mcp must be callable by AI agents via MCP, must be portable across macOS and Linux, must be extensible by users writing handler files, and must have a single way to be installed and updated.

## Decision

- Language: **Python 3.13+**.
- Packaging + workflow: **`uv`** (Rust-implemented Python package manager + venv manager).
- Distribution: a **single package**, `kvault-mcp`, containing the kernel and bundled plugins. Optional dependency extras gate any heavy or third-party-install-requiring features.
- License: **MIT**.

## Rationale

- Python 3.13: latest stable at time of writing, includes `tomllib`, native pattern matching, exception groups. Typing is mature. Target keeps us on a well-tested runtime with long support horizon.
- `uv`: faster than pip; deterministic lockfiles; ergonomic CLI; aligns with the ecosystem direction (Astral tools, PEP 621 compliance).
- Single package: simpler for users and maintainers. Bundled plugins still use the public entry-point discovery mechanism, so third-party plugins are first-class citizens and the "bundled" distinction only exists at install time.
- MIT: permissive, short, widely understood. Low friction for adoption.

## Consequences

- Users must install Python 3.13+. Acceptable given current platform availability (Homebrew, uv's Python downloader, etc.).
- One install path: `uv tool install kvault-mcp` or `uv pip install kvault-mcp` — no multi-package dependency graph to reason about in v0.1.
- Future split into `kvault-mcp` (kernel) + `kvault-plugins-core` is possible without breaking the plugin discovery contract. Not done in v0.1 because nothing forces the split now.

## Alternatives considered

- Python 3.12 floor: still acceptable; chose 3.13 because `tomllib` is present in both, and 3.13's typing ergonomics slightly better. Easy to relax later.
- Node.js: considered (qmd is TypeScript). Rejected because most of our agents and existing tooling expect Python; MCP SDK is strong in Python; Python's plugin ergonomics are well-trodden.
- Poetry / hatch / pdm: all viable; `uv` chosen for speed and momentum.
