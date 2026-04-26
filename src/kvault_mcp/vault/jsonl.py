"""JSONL reading + atomic writing. Used by every manifest builder."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Yield each line of a JSONL file as a dict. Skips blank lines.

    Malformed lines raise — manifests with bad JSON should fail loudly rather
    than be silently partial. Audit plugins catch this to report findings.
    """
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def atomic_write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    """Write rows to `path` atomically. Returns count written.

    Uses a temp file in the same directory + rename(). Either the final file
    reflects the new content in its entirety, or it reflects the previous
    content — never a partial write. Crash-safe.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, default=str))
                f.write("\n")
                count += 1
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
    return count
