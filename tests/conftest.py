from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

TOY_PLUGIN = REPO_ROOT / "tests" / "fixtures" / "toy_plugin"

PLUGIN_SOURCES: dict[str, Path] = {
    "embedding/ollama":        REPO_ROOT / "src/kvault_mcp/plugins/embedding/ollama",
    "vector_store/sqlite_vec": REPO_ROOT / "src/kvault_mcp/plugins/vector_store/sqlite_vec",
    "text_index/fts5":         REPO_ROOT / "src/kvault_mcp/plugins/text_index/fts5",
    "retriever/fts_only":      REPO_ROOT / "src/kvault_mcp/plugins/retriever/fts_only",
    "retriever/hybrid_rrf":    REPO_ROOT / "src/kvault_mcp/plugins/retriever/hybrid_rrf",
}
