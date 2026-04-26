from __future__ import annotations

from pathlib import Path
from typing import Any

from kvault_mcp.kinds.manifest_builder import BaseManifestBuilder
from kvault_mcp.vault import (
    atomic_write_jsonl,
    extract_wikilinks,
    iter_markdown_files,
)


class LineageManifestBuilder(BaseManifestBuilder):
    """Produces `lineage.jsonl` — every `[[wikilink]]` edge across the vault.

    One row per (source file, target link) pair. Downstream audits
    (`audit.lineage_dangling`) cross-reference with `frameworks.jsonl` to find
    edges pointing at entities that don't exist.
    """

    id = "manifest_builder.lineage"
    manifest_name = "lineage"

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
            "vault.manifest.lineage.built",
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
            rel = self._relative(path)
            for link in extract_wikilinks(text):
                yield {
                    "source": rel,
                    "target": link.target,
                    "alias": link.alias,
                    "section": link.section,
                }

    def _relative(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.vault_root))
        except ValueError:
            return str(path)
