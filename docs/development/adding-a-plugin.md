# Adding a plugin

This walkthrough creates a new plugin — a minimal retriever that searches markdown files by keyword — and installs it via all three discovery paths. It assumes you've read [`../concepts/plugins.md`](../concepts/plugins.md).

## Plugin directory layout

A plugin is a self-contained directory with three files:

```
<plugin_root>/<kind>/<name>/
├── plugin.toml           # manifest
├── schema.json           # config schema
└── handler.py            # implementation
```

For this walkthrough: `retriever/grep/`.

## 1. Write the manifest

`retriever/grep/plugin.toml`:

```toml
id = "grep"
kind = "retriever"
version = "0.1.0"
protocol_version = "1.0"

module = "handler"
entrypoint = "GrepRetriever"

provides = ["retriever"]
consumes_events = []
emits_events = []

config_schema = "schema.json"
install_required = []                # e.g. ["ripgrep"] if we shelled out
```

Keys explained in [`../concepts/plugins.md`](../concepts/plugins.md). Minimum required: `id`, `kind`, `version`, `protocol_version`, `module`, `entrypoint`, `provides`.

## 2. Write the config schema

`retriever/grep/schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "active":   { "type": "boolean", "default": false },
    "roots":    { "type": "array", "items": { "type": "string" }, "default": ["."] },
    "patterns": { "type": "array", "items": { "type": "string" }, "default": ["*.md"] },
    "max_results": { "type": "integer", "minimum": 1, "default": 20 }
  }
}
```

Defaults let the plugin work out of the box when `active = true` is the only config the user supplies.

## 3. Write the handler

`retriever/grep/handler.py`:

```python
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass

@dataclass
class RetrievalResult:
    id: str
    score: float
    snippet: str
    metadata: dict

class GrepRetriever:
    """Keyword retriever — searches markdown files under configured roots."""

    id = "grep"

    def __init__(self, kernel):
        self.kernel = kernel
        self.cfg = kernel.config("retriever.grep")
        self.log = kernel.logger("retriever.grep")
        self.vault_root = kernel.vault_root()

    def query(self, situation: str, k: int = 5) -> list[RetrievalResult]:
        terms = [t.lower() for t in situation.split() if len(t) > 2]
        if not terms:
            return []

        results: list[RetrievalResult] = []
        for root in self.cfg["roots"]:
            for pattern in self.cfg["patterns"]:
                for path in (self.vault_root / root).rglob(pattern):
                    try:
                        text = path.read_text(encoding="utf-8", errors="ignore").lower()
                    except OSError:
                        continue
                    score = sum(text.count(t) for t in terms)
                    if score == 0:
                        continue
                    results.append(RetrievalResult(
                        id=str(path.relative_to(self.vault_root)),
                        score=float(score),
                        snippet=self._snippet(text, terms),
                        metadata={"path": str(path)},
                    ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:min(k, self.cfg["max_results"])]

    def health(self) -> dict:
        roots_ok = all((self.vault_root / r).exists() for r in self.cfg["roots"])
        return {"ok": roots_ok, "roots": self.cfg["roots"]}

    def _snippet(self, text: str, terms: list[str], width: int = 160) -> str:
        for term in terms:
            idx = text.find(term)
            if idx >= 0:
                start = max(0, idx - width // 2)
                return text[start:start + width].replace("\n", " ")
        return ""
```

The handler speaks directly to the kernel via `self.kernel`. It never imports other plugins. It never reads `<other_plugin>/handler.py`.

## 4. Install via discovery path

Three ways to make the plugin visible to the kernel:

### A. Vault-local (fastest for prototyping)

Drop the directory into the vault:

```
<vault>/kvault.plugins/retriever/grep/
```

Add to `kvault.config.toml`:

```toml
[plugins.retriever.grep]
active = true
roots = ["AI", "Entrepreneurship", "Frameworks"]
```

Restart the MCP server. The kernel discovers, validates, instantiates.

### B. User-global

Drop into `~/.config/kvault/plugins/retriever/grep/`. Same config block in any vault that wants to use it. Plugins here are shared across all vaults the user runs.

### C. Entry-point packaged

Publish as a Python package. In `pyproject.toml`:

```toml
[project.entry-points."kvault.plugins"]
retriever_grep = "kvault_grep_retriever:GrepRetriever"
```

`pip install kvault-grep-retriever` in the kvault-mcp env. Entry points are discovered via `importlib.metadata.entry_points()`.

Precedence (if same `kind/name` appears in multiple paths): **vault-local > user-global > entry-point**.

## 5. Verify

```
kvault.plugin.list kind=retriever
# → grep (active: true, health: ok)

kvault.retrieve query="agent harness memory"
# → routes through active retriever; if `retrieval.active = "grep"` in config, uses GrepRetriever
```

## 6. Ship it

If the plugin is worth sharing:

1. Move to a standalone repo.
2. Add `pyproject.toml` with entry-point declaration.
3. Add tests (see [`testing.md`](testing.md)).
4. Publish to PyPI.

Other users install it with `pip install <your-package>` — no changes to kvault-mcp itself.

## Common pitfalls

- **Importing another plugin.** Forbidden. Use `kernel.get_active(...)` or `kernel.publish(...)`. See [`../concepts/plugins.md`](../concepts/plugins.md)'s golden rule.
- **Writing state outside `state_path()`.** Don't hardcode paths. Always call `self.kernel.state_path(category, name)` so vault-local state stays consistent.
- **Raising on health failure.** `health()` returns a dict, it doesn't raise. A plugin reporting `{"ok": false, "reason": "..."}` stays alive; a plugin that throws in health is marked broken and skipped.
- **Silent failures.** If something goes wrong, log it via `self.log` and return a reasonable empty result. The kernel never swallows exceptions but it also never expects plugins to crash.

## Checklist before merging a new plugin

- [ ] `plugin.toml` declares all required fields
- [ ] `schema.json` has `default` for every optional field
- [ ] `handler.py` has no cross-plugin imports
- [ ] `health()` is cheap and non-raising
- [ ] Tests cover the happy path (see [`testing.md`](testing.md))
- [ ] README documents config keys and any install dependencies
