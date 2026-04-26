# Testing

Tests use `pytest` plus a small `kvault_mcp.testing` harness that spins up a throwaway kernel pointed at a temp vault. No network, no global state, no shared fixtures across tests.

## Principles

- **Isolation first.** Every test gets its own vault directory and kernel instance. Tests never share state.
- **Real kernel.** Don't mock the kernel. Spin up the real one against a temp vault. Mocked kernels hide integration bugs.
- **Real plugins when they matter.** Retriever tests should use real FTS, not a mock FTS. Tests that exercise the Retriever protocol against a fake retriever belong in the kernel's unit tests, not the plugin's.
- **Mocks only at the system edge.** Network calls (Ollama, OpenAI), subprocess spawns, and filesystem I/O outside the vault are legitimate mock targets. Everything inside the vault is real.

## Directory layout

A plugin's repo:

```
<plugin>/
├── plugin.toml
├── schema.json
├── handler.py
└── tests/
    ├── conftest.py
    ├── test_query.py
    └── test_health.py
```

Tests live next to the plugin. They run via `pytest tests/`.

## The test harness

`from kvault_mcp.testing import TempVault`:

```python
from kvault_mcp.testing import TempVault
from handler import GrepRetriever

def test_grep_returns_matches():
    with TempVault() as vault:
        vault.write_file("AI/agents.md", "# Agents\nagent harness memory\n")
        vault.write_file("AI/llms.md",   "# LLMs\nprompt engineering\n")
        vault.set_config({
            "plugins": {"retriever": {"grep": {
                "active": True,
                "roots": ["AI"],
                "patterns": ["*.md"],
            }}}
        })
        kernel = vault.start_kernel()

        retriever = GrepRetriever(kernel)
        results = retriever.query("agent harness", k=5)

        assert len(results) == 1
        assert results[0].id == "AI/agents.md"
```

`TempVault` creates:
- a fresh directory in `/tmp`
- `kvault.config.toml` with the config you set
- no plugins pre-installed (you instantiate by hand, or pass `plugins=[...]`)

On exit it removes the directory.

## Testing plugin discovery

```python
def test_vault_local_plugin_discovered():
    with TempVault() as vault:
        vault.install_plugin("retriever/grep", path_to_plugin_source)
        vault.set_config({"plugins": {"retriever": {"grep": {"active": True}}}})
        kernel = vault.start_kernel()

        assert kernel.get_active(Retriever).id == "grep"
```

`install_plugin` copies the plugin tree into `<vault>/kvault.plugins/<kind>/<name>/` — exercising the real discovery path.

## Testing events

```python
def test_plugin_emits_completion_event():
    events: list[tuple[str, dict]] = []

    with TempVault() as vault:
        kernel = vault.start_kernel()
        kernel.subscribe("vault.retrieval.completed", lambda t, p: events.append((t, p)))

        retriever = GrepRetriever(kernel)
        # if retriever is event-emitting:
        retriever.query("foo")

        assert len(events) == 1
        assert events[0][0] == "vault.retrieval.completed"
```

## Testing against mocked externals

When a plugin speaks to Ollama, mock the HTTP layer, not the kernel:

```python
from unittest.mock import patch

def test_ollama_embedding_happy_path():
    with TempVault() as vault, patch("handler.urlopen") as mock_urlopen:
        mock_urlopen.return_value.read.return_value = b'{"embedding":[0.1,0.2,0.3]}'

        kernel = vault.start_kernel()
        embedder = OllamaEmbedding(kernel)

        vec = embedder.embed("hello")
        assert len(vec) == 3
```

Patch the boundary. Never patch the kernel.

## Schema validation tests

Every plugin's `schema.json` should be exercised:

```python
from jsonschema import validate, ValidationError
import json, pathlib

def test_minimal_config_passes_schema():
    schema = json.loads((pathlib.Path(__file__).parent.parent / "schema.json").read_text())
    validate({"active": True, "model": "mxbai-embed-large", "dimensions": 1024}, schema)

def test_missing_required_field_fails():
    schema = json.loads((pathlib.Path(__file__).parent.parent / "schema.json").read_text())
    with pytest.raises(ValidationError):
        validate({"active": True}, schema)  # missing model + dimensions
```

## Integration test tier

For plugins that depend on real services (Ollama, a model), create a separate `tests/integration/` directory. Mark with `pytest.mark.integration` and skip by default:

```python
@pytest.mark.integration
def test_real_ollama_roundtrip():
    if not _ollama_available():
        pytest.skip("ollama not running")
    ...
```

Run unit tests on every commit; run integration tests explicitly (`pytest -m integration`) when the environment supports it.

## What not to test

- **Don't test the kernel from a plugin's tests.** The kernel has its own test suite.
- **Don't test what the schema already validates.** If `required: ["model"]` is in the schema, you don't need a handler test for "raises on missing model" — the kernel rejects the plugin at instantiation.
- **Don't assert on log messages.** They're for humans. Assert on return values and emitted events.

## Running tests

```
pytest                         # all unit tests
pytest -m integration          # real-services tier
pytest -k "test_grep"          # subset by name
pytest --cov=handler           # coverage for the handler module
```

CI runs only unit tests. Integration tests are a local / pre-release concern until the project has a service-matrix CI.
