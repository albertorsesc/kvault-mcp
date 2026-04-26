from __future__ import annotations

from pathlib import Path
from typing import Any

from kvault_mcp.kinds.manifest_builder import BaseManifestBuilder
from kvault_mcp.vault import (
    atomic_write_jsonl,
    iter_markdown_files,
    parse_frontmatter,
)


class FrameworksManifestBuilder(BaseManifestBuilder):
    """Produces `frameworks.jsonl` — one row per framework note.

    A framework note is any markdown file under the configured roots. The row
    captures path, title, frontmatter fields, and size — enough to drive
    downstream audits (orphan hubs, stale frameworks) without re-walking
    the filesystem.
    """

    id = "manifest_builder.frameworks"
    manifest_name = "frameworks"

    def __init__(self, kernel: Any) -> None:
        super().__init__(kernel)
        out_rel = Path(self.cfg["output"])
        self._output = out_rel if out_rel.is_absolute() else self.vault_root / out_rel
        self._roots = list(self.cfg["roots"])
        self._extensions = tuple(self.cfg["extensions"])

    def build(self) -> dict[str, Any]:
        rows = list(self._rows())
        count = atomic_write_jsonl(self._output, rows)
        self.kernel.publish(
            "vault.manifest.frameworks.built",
            {"plugin_id": self.id, "count": count, "path": str(self._output)},
        )
        return {"count": count, "path": str(self._output)}

    def tool_build(self) -> dict[str, Any]:
        return self.build()

    def _rows(self):
        for path in iter_markdown_files(self.vault_root, self._roots, self._extensions):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            fm = parse_frontmatter(text)
            title = self._title(text, path)
            rel = self._relative(path)
            yield {
                "id": rel,
                "title": title,
                "path": rel,
                "size_bytes": path.stat().st_size,
                "frontmatter": fm,
            }

    def _relative(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.vault_root))
        except ValueError:
            return str(path)

    @staticmethod
    def _title(text: str, path: Path) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        return path.stem
