from __future__ import annotations

from pathlib import Path
from typing import Any

from kvault_mcp.kinds.manifest_builder import BaseManifestBuilder
from kvault_mcp.vault import atomic_write_jsonl


class CapabilitiesManifestBuilder(BaseManifestBuilder):
    """Produces `vault-capabilities.jsonl` — one row per discovered plugin.

    Pure derivation from `kernel.loaded_plugins()`. Never imports any plugin
    module. Regenerable at any time.
    """

    id = "manifest_builder.capabilities"
    manifest_name = "vault-capabilities"

    def __init__(self, kernel: Any) -> None:
        super().__init__(kernel)
        out_rel = Path(self.cfg["output"])
        self._output = out_rel if out_rel.is_absolute() else self.vault_root / out_rel

    def build(self) -> dict[str, Any]:
        rows = list(self._rows())
        count = atomic_write_jsonl(self._output, rows)
        self.kernel.publish(
            "vault.manifest.capabilities.built",
            {"plugin_id": self.id, "count": count, "path": str(self._output)},
        )
        return {"count": count, "path": str(self._output)}

    def tool_build(self) -> dict[str, Any]:
        return self.build()

    def _rows(self):
        for lp in self.kernel.loaded_plugins():
            yield {
                "id": lp.spec.id,
                "kind": lp.spec.kind,
                "name": lp.spec.name,
                "version": lp.spec.version,
                "protocol_version": lp.spec.protocol_version,
                "source": lp.spec.source,
                "source_path": str(lp.spec.source_path),
                "provides": list(lp.spec.provides),
                "consumes_events": list(lp.spec.consumes_events),
                "emits_events": list(lp.spec.emits_events),
                "active": lp.active,
                "health": lp.health,
                "tools": sorted(lp.spec.tools.keys()),
            }
