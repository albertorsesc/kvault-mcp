# External APIs

Reference for the third-party APIs kvault-mcp plugins speak to. Verified against versions current as of 2026-04-24.

## 1. Ollama HTTP embedding API

**What it is.** Ollama is a local LLM runtime on `http://localhost:11434`. Used by the embedding plugin.

**Version.** Tested against Ollama `0.5.x`–`0.6.x`. `/api/embed` stable since `0.4`. Legacy `/api/embeddings` superseded.

### Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/embed` | POST | Generate embeddings (canonical) |
| `/api/embeddings` | POST | Legacy single-embedding (deprecated) |
| `/api/tags` | GET | List local models |
| `/api/show` | POST | Model details |
| `/api/version` | GET | Server version |

### `/api/embed` request

```json
{
  "model": "nomic-embed-text",
  "input": ["first chunk", "second chunk"],
  "truncate": true,
  "keep_alive": "5m",
  "options": {}
}
```

| Field | Type | Req | Notes |
|---|---|---|---|
| `model` | string | yes | e.g. `nomic-embed-text:latest` |
| `input` | string \| string[] | yes | Polymorphic |
| `truncate` | bool | no (default true) | ⚠️ broken since 0.13.5 — pre-truncate client-side |
| `keep_alive` | string | no (default `"5m"`) | `"0"`=unload now, `-1`=forever |
| `options` | object | no | Usually empty for embeddings |
| `dimensions` | int | no | ⚠️ bug: sent twice, logs "invalid option"; avoid unless Matryoshka |

### `/api/embed` response

```json
{
  "model": "nomic-embed-text",
  "embeddings": [[0.01, -0.02], []],
  "total_duration": 123456789,
  "load_duration": 12345678,
  "prompt_eval_count": 42
}
```

Vectors returned by `/api/embed` are **L2-normalized** (unit length). Cosine and dot-product rank identically on them.

### Errors

HTTP 4xx/5xx with `{"error": "<message>"}`. Common: 404 for unpulled model, 400 for oversize input, 500 for runtime errors. No server-side rate limiting. No documented batch-size cap; keep practical batches to 32–128.

### List / check models

- `GET /api/tags` → `{"models": [{"name", "modified_at", "size", "digest", "details": {"family"}}]}`
- `POST /api/show` with `{"model": "<name>"}` → 404 if not pulled, else modelfile/params/template.

### Minimal Python (stdlib only)

```python
from __future__ import annotations

import json
from typing import Any
from urllib import request, error


def ollama_embed(
    texts: list[str],
    model: str = "nomic-embed-text",
    host: str = "http://localhost:11434",
    timeout: float = 60.0,
) -> list[list[float]]:
    body = json.dumps({"model": model, "input": texts}).encode("utf-8")
    req = request.Request(
        url=f"{host}/api/embed",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            payload: dict[str, Any] = json.loads(resp.read())
    except error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ollama HTTP {e.code}: {detail}") from e
    except error.URLError as e:
        raise RuntimeError(f"ollama unreachable at {host}: {e.reason}") from e

    vectors = payload.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise RuntimeError(f"unexpected response shape: {payload!r}")
    return vectors


def ollama_model_exists(model: str, host: str = "http://localhost:11434") -> bool:
    try:
        with request.urlopen(f"{host}/api/tags", timeout=5.0) as resp:
            data = json.loads(resp.read())
    except error.URLError:
        return False
    names = {m.get("name") for m in data.get("models", [])}
    return model in names or f"{model}:latest" in names
```

### Equivalent curl

```bash
curl -s http://localhost:11434/api/embed \
  -H 'Content-Type: application/json' \
  -d '{"model":"nomic-embed-text","input":["hello world","kvault rocks"]}'
```

### Gotchas

- `urllib.request.urlopen` opens a new socket per call — use `http.client.HTTPConnection` + keep-alive for high-throughput re-indexing, or batch larger `input` arrays.
- Default `urllib` timeout is none — always pass `timeout=`. First call can cold-load a model (5–30s); use ≥60s.
- `truncate` effectively broken since 0.13.5 — pre-truncate chunks to the model's context (usually 512 or 8192 tokens).
- Vectors are L2-normalized — re-embed queries with the **same model** at query time.
- Record model + dimension with the collection (see ADR-0008); refuse mismatched loads.

### Reference

- https://docs.ollama.com/api/embed
- https://github.com/ollama/ollama/blob/main/docs/api.md
- https://docs.ollama.com/capabilities/embeddings

## 2. sqlite-vec

**What it is.** SQLite extension providing vector search via `vec0` virtual tables. Brute-force k-NN, no ANN index.

**Version.** `sqlite-vec 0.1.9` (2026-03-31). Dual Apache-2.0 / MIT. PyPI: `sqlite-vec`. Prebuilt wheels for macOS arm64, macOS x86_64, Linux x86_64, Linux aarch64, Windows x86_64.

### Installation

```bash
pip install sqlite-vec
```

**Critical macOS Python requirement.** Apple system Python and some pyenv builds compile `sqlite3` without `enable_load_extension`, raising `AttributeError: 'sqlite3.Connection' object has no attribute 'enable_load_extension'`. Install via Homebrew (`brew install python@3.13`) or build pyenv Python with `PYTHON_CONFIGURE_OPTS="--enable-loadable-sqlite-extensions"`.

### Load

```python
import sqlite3
import sqlite_vec

db = sqlite3.connect("vault.db")
db.enable_load_extension(True)
sqlite_vec.load(db)
db.enable_load_extension(False)
```

### DDL

```sql
CREATE VIRTUAL TABLE chunks USING vec0(
    chunk_id INTEGER PRIMARY KEY,
    embedding float[768],
    collection TEXT PARTITION KEY,
    source_path TEXT,
    +updated_at INTEGER
);
```

Column flavors:
- **Vector**: `float[N]`, `int8[N]`, `bit[N]`. Dimension fixed at creation.
- **PARTITION KEY**: physical partitioning; enables partition-prune on `WHERE`.
- **Auxiliary** (plain typed): stored in shadow table, retrievable.
- **Metadata** (`+` prefix): inline, unindexed, fast read.
- **PRIMARY KEY**: becomes `rowid`. Must be INTEGER unless opting into text keys.

### INSERT

```python
import numpy as np
from sqlite_vec import serialize_float32

db.execute(
    "INSERT INTO chunks(chunk_id, embedding, collection, source_path) VALUES (?, ?, ?, ?)",
    (42, serialize_float32([0.1, 0.2, 0.3]), "notes_v1", "/vault/note.md"),
)

arr = np.asarray([0.1, 0.2], dtype=np.float32)  # MUST be float32, not float64
db.execute(
    "INSERT INTO chunks(chunk_id, embedding, collection, source_path) VALUES (?, ?, ?, ?)",
    (43, arr, "notes_v1", "/vault/note2.md"),
)
```

`serialize_float32(list[float])` = `struct.pack(f"{n}f", *vec)` — same on-disk bytes as a `float32` ndarray buffer.

Dimension mismatch → `sqlite3.OperationalError: Dimension mismatch: expected 768, got 512`. Plugin should catch and return structured error.

### k-NN query

```sql
SELECT chunk_id, distance, source_path
FROM chunks
WHERE embedding MATCH ?
  AND collection = ?
  AND k = ?
ORDER BY distance;
```

```python
rows = db.execute(
    "SELECT chunk_id, distance, source_path FROM chunks "
    "WHERE embedding MATCH ? AND collection = ? AND k = ? ORDER BY distance",
    (serialize_float32(query_vec), "notes_v1", 10),
).fetchall()
```

**`k = ?` is mandatory** with `MATCH` on vec0 — it's the virtual table's bound hint.

### Distance functions

| Function | Semantics |
|---|---|
| `vec_distance_cosine(a, b)` | `1 - cosine_similarity` |
| `vec_distance_l2(a, b)` | Euclidean |
| `vec_distance_hamming(a, b)` | Bit vectors only |

Implicit `distance` column in MATCH queries = L2. Ollama vectors are pre-normalized so L2 and cosine rank identically.

### Combining with FTS5

**Same DB file, same connection, separate tables, separate queries, fuse in Python with RRF.** Do NOT try to JOIN vec0 with fts5 virtual tables.

```python
db = sqlite3.connect("vault.db")
db.enable_load_extension(True)
sqlite_vec.load(db)
db.enable_load_extension(False)

db.execute("CREATE VIRTUAL TABLE fts USING fts5(body, content='', tokenize='porter unicode61')")
db.execute("CREATE VIRTUAL TABLE vec USING vec0(chunk_id INTEGER PRIMARY KEY, embedding float[768])")
```

### Known limits

- **Brute-force only.** O(N*D) per query. Benchmark: 100k × 384-dim under 100ms; 1M × 1536-dim slows dramatically. Past ~500k chunks, revisit.
- **Max dimensions** ⚠️ unverified — no hard ceiling documented. Stay ≤ 1536 for responsiveness.
- **Concurrency**: SQLite model — many readers OR one writer. Batch inserts in a single transaction.
- **No ANN yet**: tracked at `asg017/sqlite-vec#25`. Design the vector_store plugin with swappable algorithm.

### Reference

- https://github.com/asg017/sqlite-vec
- https://alexgarcia.xyz/sqlite-vec/python.html

## 3. SQLite FTS5

**What it is.** SQLite's built-in full-text search virtual table. BM25-ranked.

**Version.** Any SQLite ≥ 3.43 compiled with FTS5 (check: `SELECT sqlite_compileoption_used('ENABLE_FTS5');`). `contentless_delete=1` requires ≥ 3.43.

### Schema pattern: contentless-delete (best for markdown vault)

```sql
CREATE VIRTUAL TABLE fts USING fts5(
    source_path UNINDEXED,
    body,
    tokenize = 'porter unicode61 remove_diacritics 2',
    content = '',
    contentless_delete = 1
);
```

Why:
- `content=''` — don't duplicate markdown; files on disk are source of truth.
- `contentless_delete=1` — allow DELETE by rowid without full rebuild.
- `UNINDEXED source_path` — stored for snippet citation, not tokenized.
- `porter unicode61` — Unicode word-split + English stemming.

### Tokenizer choice

| Tokenizer | Use when |
|---|---|
| `unicode61` | Multi-lingual or exact-token matching |
| `porter unicode61` | **Default for kvault** — English markdown |
| `trigram` | Substring / fuzzy / identifier search |

### BM25 query

```sql
SELECT
    source_path,
    bm25(fts)       AS score,
    snippet(fts, 1, '<b>', '</b>', '…', 16) AS preview
FROM fts
WHERE fts MATCH ?
ORDER BY bm25(fts)
LIMIT 20;
```

- `bm25(fts)` returns a **smaller-is-better** real number. Negate if you want larger=better.
- `snippet(fts, col_index, start_tag, end_tag, ellipsis, tokens)` returns highlighted fragment.
- `highlight(fts, col_index, start_tag, end_tag)` wraps every match in full column text.

### Manual rebuild

```python
def reindex_file(db, path: str, body: str, rowid: int) -> None:
    with db:
        db.execute("DELETE FROM fts WHERE rowid = ?", (rowid,))
        db.execute(
            "INSERT INTO fts(rowid, source_path, body) VALUES (?, ?, ?)",
            (rowid, path, body),
        )
```

```sql
-- After large batch insert
INSERT INTO fts(fts) VALUES ('optimize');
```

`INSERT INTO fts(fts) VALUES ('rebuild')` only works for **external-content** tables. For contentless, "rebuild" = DROP + CREATE + re-ingest.

### Gotchas

- FTS5 query syntax is not SQL: space = AND, supports `OR`, `NOT`, `"quoted phrase"`, `col:term`, `term*`, `NEAR(a b, 5)`. Untrusted input must be double-quoted as a phrase.
- `bm25(fts, 1.0, 2.0)` weights columns.
- Contentless tables: no UPDATE. Update = delete + insert.
- Porter stemmer is English-only.

### Reference

- https://www.sqlite.org/fts5.html

## 4. Reciprocal Rank Fusion

**What it is.** Rank aggregation for fusing FTS5 (BM25) + sqlite-vec (distance) ranked lists.

**Version.** Algorithm. Cormack, Clarke, Büttcher (2009).

### Formula

For each doc `d` and each list `L_i` where `d` has rank `r_i(d)` (1-indexed):

```
RRF_score(d) = Σ_i  1 / (k + r_i(d))
```

`k = 60` is the standard default. Docs absent from a list contribute 0. Higher = better.

### Why it works for FTS5 + sqlite-vec

BM25 scores ≈ `[-20, 0]`, cosine distance ≈ `[0, 2]`. Scale-incomparable, and min-max / z-score normalization is brittle. RRF discards magnitudes and uses only ranks — order survives any monotonic transform.

### Reference implementation

```python
from __future__ import annotations

from collections.abc import Iterable, Sequence


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Iterable[str]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Fuse N ranked lists of doc IDs into one ranked list."""
    scores: dict[str, float] = {}
    for one_list in ranked_lists:
        seen: set[str] = set()
        for rank, doc_id in enumerate(one_list, start=1):
            if doc_id in seen:
                continue
            seen.add(doc_id)
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
```

### Pitfalls

- Cross-list duplicates are the whole point — don't de-dupe across lists.
- Within-list duplicates shouldn't exist for rowid-based IDs, but guard anyway.
- Ties: for reproducibility sort by `(score, doc_id)`.
- `k` tuning range: 40–100.
- Length imbalance: cap both lists to the same top-K before fusing.

### Reference

- https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf

## 5. Python 3.13 `entry_points`

**What it is.** stdlib plugin discovery. kvault-mcp uses `entry_points(group="kvault.plugins")` at kernel startup.

**Version.** Python 3.13+.

### API

```python
from importlib.metadata import entry_points, EntryPoints

eps: EntryPoints = entry_points(group="kvault.plugins")
for ep in eps:
    print(ep.name, ep.value, ep.group)
    plugin_cls = ep.load()

matches = entry_points(group="kvault.plugins").select(name="vector_store_sqlite_vec")
if not matches:
    raise LookupError("plugin not installed")
plugin_cls = next(iter(matches)).load()
```

### Version differences

| Python | Behavior |
|---|---|
| 3.11 | Transitional — `SelectableGroups` returned with no args |
| 3.12 | Always returns `EntryPoints` |
| 3.13 | `EntryPoint` no longer tuple-indexable — use `.name`, `.value`, `.group` |

### Finding a plugin's `plugin.toml`

```python
import importlib
from importlib.metadata import entry_points
from pathlib import Path

ep = next(iter(entry_points(group="kvault.plugins").select(name="vector_store_sqlite_vec")))
plugin_cls = ep.load()

module = importlib.import_module(plugin_cls.__module__)
plugin_dir = Path(module.__file__).parent
plugin_toml = plugin_dir / "plugin.toml"
```

### Declaring (plugin side)

```toml
[project.entry-points."kvault.plugins"]
vector_store_sqlite_vec = "kvault_vector_sqlite.plugin:SqliteVecPlugin"
```

### Gotchas

- Entry points are per-interpreter. `pip install -e` must use the same Python the kernel runs.
- Cache the `entry_points()` result at startup.
- `.load()` triggers module import. First call can be slow.
- Two plugins with the same name in the same group are both returned; enforce uniqueness at kernel level.

### Reference

- https://docs.python.org/3.13/library/importlib.metadata.html

## 6. MCP Python SDK (stdio)

**What it is.** Anthropic's official Python SDK for Model Context Protocol servers.

**Version.** `mcp 1.27.0` (2026-04-02). Python 3.10+. Install: `pip install "mcp[cli]"`.

### Two API surfaces

- `mcp.server.fastmcp.FastMCP` — high-level, decorator-only, auto type-hint introspection.
- `mcp.server.lowlevel.Server` — **what kvault-mcp uses** because the kernel needs to register tools dynamically after plugin discovery.

### Minimal stdio server (low-level)

```python
from __future__ import annotations

import asyncio
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions


server: Server = Server("kvault")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search",
            description="Hybrid (FTS5 + vector) search across the vault.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name == "search":
        query = arguments["query"]
        top_k = arguments.get("top_k", 10)
        return [types.TextContent(type="text", text=f"searched {query!r} top_k={top_k}")]
    raise ValueError(f"unknown tool: {name}")


async def main() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="kvault",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(tools_changed=True),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
```

### Dynamic tool registration pattern

```python
class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, types.Tool] = {}
        self._handlers: dict[str, object] = {}

    def register(self, tool: types.Tool, handler) -> None:
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler

    def all(self) -> list[types.Tool]:
        return list(self._tools.values())

    def handler(self, name: str):
        return self._handlers[name]


registry = ToolRegistry()


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return registry.all()


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]):
    return await registry.handler(name)(**arguments)
```

### Gotchas

- stdio = stdin/stdout is the channel. **Never `print()`** from handlers; log to stderr.
- Return type for `@server.call_tool()` is `list[ContentBlock]`.
- Tool names: stick to `[a-z_][a-z0-9_]*`. Some clients reject hyphens/dots.
- `inputSchema` is Draft 2020-12.
- Blocking DB calls in handlers stall the event loop. Wrap in `asyncio.to_thread(...)`.
- Pin exactly: `mcp==1.27.*`. 1.x has API churn.

### Reference

- https://github.com/modelcontextprotocol/python-sdk
- https://pypi.org/project/mcp/

## 7. jsonschema (Python)

**What it is.** JSON Schema validation. Used in kvault-mcp to validate plugin config against each plugin's `schema.json`.

**Version.** `jsonschema 4.26.0` (stable). Python 3.8+.

### Draft 2020-12 validator

```python
from jsonschema import Draft202012Validator

validator = Draft202012Validator(schema)
validator.check_schema(schema)
errors = sorted(validator.iter_errors(cfg), key=lambda e: e.path)
```

### Fill-in-defaults

Stock `jsonschema` does NOT populate `default`. Extend a validator:

```python
from __future__ import annotations

from typing import Any
from jsonschema import Draft202012Validator, validators


def _extend_with_default(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        if isinstance(instance, dict):
            for prop, subschema in properties.items():
                if "default" in subschema:
                    instance.setdefault(prop, subschema["default"])
        yield from validate_properties(validator, properties, instance, schema)

    return validators.extend(validator_class, {"properties": set_defaults})


DefaultFillingValidator = _extend_with_default(Draft202012Validator)


def validate_and_fill(schema: dict[str, Any], config: dict[str, Any]) -> list[str]:
    validator = DefaultFillingValidator(schema)
    errors = []
    for err in sorted(validator.iter_errors(config), key=lambda e: e.path):
        path = "/".join(map(str, err.absolute_path)) or "<root>"
        errors.append(f"{path}: {err.message}")
    return errors
```

### Gotchas

- Defaults must themselves validate.
- Defaults fill BEFORE required/type checks — plan top-down.
- `format` is opt-in — pass `format_checker=Draft202012Validator.FORMAT_CHECKER`.
- Don't mix draft versions.

### Reference

- https://pypi.org/project/jsonschema/
- https://python-jsonschema.readthedocs.io/en/stable/faq/

## Appendix: Version matrix

| Dependency | Version tested | Python support | Notes |
|---|---|---|---|
| Ollama server | 0.5.x – 0.6.x | n/a (HTTP) | `/api/embed` stable since 0.4; `truncate` broken since 0.13.5 |
| `sqlite-vec` (PyPI) | 0.1.9 | 3.8+ | macOS arm64 wheel; brute-force only |
| SQLite | ≥ 3.43 | n/a | `contentless_delete=1` needs 3.43+ |
| `mcp` (PyPI) | 1.27.0 | 3.10+ | Pin exactly — 1.x has API churn |
| stdlib `importlib.metadata` | 3.13 | 3.13 | EntryPoint not tuple-indexable |
| `jsonschema` (PyPI) | 4.26.0 | 3.8+ | Draft 2020-12 + extend for defaults |

## Pinning recommendation

```toml
dependencies = [
    "sqlite-vec>=0.1.9,<0.2",
    "mcp==1.27.*",
    "jsonschema>=4.26,<5",
]
```

Ollama is system dep, installed separately (brew install ollama).
