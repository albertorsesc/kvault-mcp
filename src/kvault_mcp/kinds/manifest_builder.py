from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from kvault_mcp.kinds._base import BasePlugin
from kvault_mcp.kinds._registry import register_provider_type


@runtime_checkable
class ManifestBuilder(Protocol):
    id: str
    manifest_name: str

    def build(self) -> dict[str, Any]: ...
    def health(self) -> dict[str, Any]: ...


class BaseManifestBuilder(BasePlugin):
    manifest_name: str = ""

    def build(self) -> dict[str, Any]:
        raise NotImplementedError


register_provider_type("manifest_builder", ManifestBuilder)
