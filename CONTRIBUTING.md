# Contributing to kvault-mcp

Thanks for your interest. kvault-mcp is pre-1.0 and opinionated. Contributions that align with the architecture in [`docs/`](docs/) are welcome; contributions that contradict it will be sent back for revision or closed.

## Before you open a PR

1. **Read [`docs/architecture.md`](docs/architecture.md).** The meta architecture is frozen. Plugins, kinds, core, testing — each concept has its proper directory. Anything that blurs those lines gets pushed back.
2. **Skim the ADRs in [`docs/adr/`](docs/adr/).** If your change contradicts an ADR, open an issue first — not a PR.
3. **Check there is no open issue covering the same work.** If there is, comment on it before starting.

## Development setup

```bash
git clone <fork-or-repo> kvault-mcp
cd kvault-mcp
uv sync --all-extras
uv run pytest -q
uv run ruff check .
```

Python 3.13+ is required. macOS and Linux are supported. Install uv via `brew install uv` or the uv installer.

**macOS SQLite note.** The `vector_store/sqlite_vec` plugin requires a Python built with `--enable-loadable-sqlite-extensions`. Apple's system Python is not built that way. Use Homebrew Python (`brew install python@3.13`) or uv's managed Python.

## Standards (non-negotiable)

- **SOLID first.** One responsibility per file. New logic that mixes concerns gets split before merge.
- **No plugin-to-plugin imports.** Plugins coordinate via `kernel.get_active(Protocol)` (sync) or `kernel.publish` / `kernel.subscribe` (async) — never by importing each other.
- **Each concept in its proper directory.** Kernel machinery → `src/kvault_mcp/core/`. Plugin kind (Protocol + Base) → `src/kvault_mcp/kinds/<kind>.py`. Implementations → `src/kvault_mcp/plugins/<kind>/<name>/`. Don't cross these lines.
- **Tests are required.** Every fix ships with a regression test. Every new plugin ships with an integration test using `TempVault`.
- **Ruff clean.** `uv run ruff check .` returns no errors before you open the PR.
- **No backwards-compat shims.** Break cleanly; document in `CHANGELOG.md`.

## Adding a new plugin implementation

See [`docs/development/adding-a-plugin.md`](docs/development/adding-a-plugin.md) for the walkthrough. Short version:

1. Drop a directory at `src/kvault_mcp/plugins/<kind>/<name>/` with `plugin.toml` + `schema.json` + `handler.py`.
2. Handler subclasses the matching base class from `src/kvault_mcp/kinds/<kind>.py`.
3. Register the entry point in `pyproject.toml` under `[project.entry-points."kvault.plugins"]`.
4. Add an integration test under `tests/test_plugin_<kind>_<name>.py`.

## Adding a new plugin kind

Rare. Open an issue first.

1. Add `src/kvault_mcp/kinds/<kind>.py` with Protocol + Base class + `register_provider_type(...)` call at module load.
2. Re-export from `src/kvault_mcp/kinds/__init__.py`.
3. Document the kind in `docs/concepts/`.

Nothing in `core/` should need to change.

## Commit and PR etiquette

- One concern per commit. Refactor commits separate from behavior-change commits.
- Commit message: imperative mood. `fix: state_path escape via .. traversal` / `feat: add Anthropic embedding plugin`.
- PR description: link the issue, summarize the decision, note the ADR if relevant.
- Small is beautiful. A 50-line PR gets reviewed in 10 minutes. A 1000-line PR does not.

## Reporting bugs

Open an issue with:
- kvault-mcp version + Python version + OS
- Reproduction: minimal `kvault.config.toml` + one failing tool call or script
- Expected vs actual behavior

## Reporting security issues

See [`SECURITY.md`](SECURITY.md). Do NOT open public issues for security reports.

## License

Contributions are under the MIT license — the same as the rest of the repo. By opening a PR you affirm you have the right to license your contribution this way.
