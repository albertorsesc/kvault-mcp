"""Walk vault directories and yield markdown file paths."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path


def iter_markdown_files(
    vault_root: Path,
    roots: list[str],
    extensions: tuple[str, ...] = (".md",),
) -> Iterator[Path]:
    """Yield every file matching `extensions` under each root.

    `roots` are relative to `vault_root` unless absolute. Hidden directories
    (dotfile dirs like `.git`, `.obsidian`) are skipped automatically.
    """
    ext_lower = tuple(e.lower() for e in extensions)
    for root in roots:
        base = Path(root) if Path(root).is_absolute() else vault_root / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in ext_lower:
                continue
            if any(part.startswith(".") for part in path.relative_to(base).parts):
                continue
            yield path
