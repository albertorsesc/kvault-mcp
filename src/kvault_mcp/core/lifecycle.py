from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kvault_mcp.core.config import ConfigResolver
from kvault_mcp.core.discovery import DiscoveredPlugin
from kvault_mcp.core.logger import make_logger


@dataclass
class LoadedPlugin:
    spec: DiscoveredPlugin
    instance: object
    config: dict[str, Any]
    health: dict[str, Any]
    active: bool


def _load_schema(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def _import_handler_class(plugin: DiscoveredPlugin) -> type:
    """Load the entrypoint class from the plugin directory."""
    if plugin.source == "entry_point":
        mod = importlib.import_module(plugin.module)
        return getattr(mod, plugin.entrypoint)

    module_name = f"_kvault_plugin_{plugin.kind}_{plugin.name}"
    module_file = plugin.plugin_dir / f"{plugin.module}.py"
    if not module_file.exists():
        raise FileNotFoundError(f"plugin module missing: {module_file}")
    spec = importlib.util.spec_from_file_location(module_name, module_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load plugin: {plugin.id}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, plugin.entrypoint)


class PluginLifecycle:
    """Loads discovered plugins, wires them to the kernel, registers them."""

    def __init__(self, kernel: Any, config_resolver: ConfigResolver) -> None:
        self._kernel = kernel
        self._config = config_resolver
        self._log = make_logger("kernel.lifecycle")

    def load(self, discovered: list[DiscoveredPlugin]) -> list[LoadedPlugin]:
        loaded: list[LoadedPlugin] = []
        for plugin in discovered:
            try:
                result = self._load_one(plugin)
            except Exception as exc:
                self._log.exception(
                    "plugin load failed",
                    extra={"plugin_id": plugin.id, "event": "lifecycle.load_failed"},
                )
                loaded.append(
                    LoadedPlugin(
                        spec=plugin,
                        instance=None,
                        config={},
                        health={"ok": False, "reason": str(exc)},
                        active=False,
                    )
                )
                continue
            loaded.append(result)
        return loaded

    def _load_one(self, plugin: DiscoveredPlugin) -> LoadedPlugin:
        schema = _load_schema(plugin.config_schema_path)
        resolved = self._config.resolve_plugin(plugin.id, schema)
        # Make config visible to the kernel BEFORE any plugin __init__ runs —
        # BasePlugin.__init__ calls kernel.config(self.id) to pull its config.
        self._kernel._set_plugin_config(plugin.id, resolved)
        active = bool(resolved.get("active", False))

        cls = _import_handler_class(plugin)
        instance = cls(self._kernel) if active else None
        health: dict[str, Any] = {"ok": True}
        if instance is not None and hasattr(instance, "health"):
            try:
                health = instance.health() or {"ok": True}
            except Exception as exc:
                health = {"ok": False, "reason": f"health raised: {exc!r}"}
        # `active` reflects config + successful instantiation. Health is a
        # runtime signal, not a gate — consumers inspect it via plugin.list
        # or the plugin's own health() call. A failing health check should
        # surface the plugin to diagnostics, not hide it from the registry.
        return LoadedPlugin(
            spec=plugin,
            instance=instance,
            config=resolved,
            health=health,
            active=active and instance is not None,
        )
