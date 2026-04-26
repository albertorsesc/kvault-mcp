from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from kvault_mcp.core.config import ConfigResolver
from kvault_mcp.core.discovery import discover_plugins
from kvault_mcp.core.eventbus import EventBus
from kvault_mcp.core.lifecycle import LoadedPlugin, PluginLifecycle
from kvault_mcp.core.logger import make_logger
from kvault_mcp.core.registry import ServiceRegistry
from kvault_mcp.core.state import StatePathResolver

P = TypeVar("P")


class KernelCore:
    """The object passed to every plugin. Narrow surface, stable contract."""

    def __init__(
        self,
        vault_root: Path,
        user_global_root: Path | None = None,
    ) -> None:
        self._vault_root = Path(vault_root).resolve()
        self._user_global_root = user_global_root
        self._config = ConfigResolver(self._vault_root)
        kernel_cfg = self._config.kernel_section()
        self._log_level = str(kernel_cfg.get("log_level", "info"))
        self._log = make_logger("kernel", level=self._log_level)
        self._events = EventBus()
        self._registry = ServiceRegistry()
        self._state = StatePathResolver(self._vault_root, create=True)
        self._loaded: list[LoadedPlugin] = []
        self._plugin_configs: dict[str, dict[str, Any]] = {}

    def start(self) -> None:
        discovered = discover_plugins(self._vault_root, self._user_global_root)
        self._log.info(
            "discovered plugins",
            extra={"event": "kernel.discovered", "count": len(discovered)},
        )
        lifecycle = PluginLifecycle(self, self._config)
        self._loaded = lifecycle.load(discovered)
        for lp in self._loaded:
            self._plugin_configs[lp.spec.id] = lp.config
            if lp.instance is None or not lp.active:
                continue
            self._register_by_provides(lp)
            self._subscribe_plugin_events(lp)
        # Re-evaluate health AFTER all wiring completes. Plugins that depend on
        # other plugins via the registry (e.g. retriever/fts_only needs
        # text_index) show stale health from their __init__-time snapshot
        # otherwise; this pass reflects the fully-wired system.
        self._refresh_health()
        self._events.publish("vault.kernel.started", {"plugin_count": len(self._loaded)})

    def _refresh_health(self) -> None:
        for lp in self._loaded:
            if lp.instance is None or not hasattr(lp.instance, "health"):
                continue
            try:
                lp.health = lp.instance.health() or {"ok": True}
            except Exception as exc:
                lp.health = {"ok": False, "reason": f"health raised: {exc!r}"}

    def _register_by_provides(self, lp: LoadedPlugin) -> None:
        from kvault_mcp.kinds import PROVIDER_TYPES

        for provide in lp.spec.provides:
            proto = PROVIDER_TYPES.get(provide)
            if proto is None:
                self._log.warning(
                    "unknown provides-type; skipping registration",
                    extra={"plugin_id": lp.spec.id, "event": "kernel.unknown_provides"},
                )
                continue
            self._registry.register(proto, lp.spec.id, lp.instance, lp.active)

    def _subscribe_plugin_events(self, lp: LoadedPlugin) -> None:
        inst = lp.instance
        if inst is None:
            return
        for event_type in lp.spec.consumes_events:
            method_name = "on_" + event_type.replace(".", "_")
            handler = getattr(inst, method_name, None)
            if handler is None:
                continue
            self._events.subscribe(event_type, handler)

    # ── Public API (plugin-facing) ────────────────────────────────────────

    def get_active(self, protocol: type[P]) -> P | None:
        return self._registry.get_active(protocol)

    def get_all(self, protocol: type[P]) -> list[P]:
        return self._registry.get_all(protocol)

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        self._events.publish(event_type, payload)

    def subscribe(
        self, event_type: str, handler: Callable[[str, dict[str, Any]], None]
    ) -> None:
        self._events.subscribe(event_type, handler)

    def state_path(self, category: str, name: str | None = None) -> Path:
        return self._state.path(category, name)

    def config(self, plugin_id: str) -> dict[str, Any]:
        return dict(self._plugin_configs.get(plugin_id, {}))

    def _set_plugin_config(self, plugin_id: str, config: dict[str, Any]) -> None:
        """Internal API used by lifecycle to seed a plugin's resolved config.

        Must be called BEFORE the plugin's __init__ runs, because
        BasePlugin.__init__ pulls via kernel.config(self.id). Single leading
        underscore marks this as kernel-internal; not part of the public
        plugin-facing surface.
        """
        self._plugin_configs[plugin_id] = dict(config)

    def logger(self, plugin_id: str) -> logging.Logger:
        return make_logger(plugin_id, level=self._log_level)

    def vault_root(self) -> Path:
        return self._vault_root

    # ── Kernel-internal views (used by server/tests) ──────────────────────

    def loaded_plugins(self) -> list[LoadedPlugin]:
        return list(self._loaded)

    def plugin_by_id(self, plugin_id: str) -> LoadedPlugin | None:
        for lp in self._loaded:
            if lp.spec.id == plugin_id:
                return lp
        return None

    def health_summary(self) -> dict[str, Any]:
        return {
            "vault_root": str(self._vault_root),
            "plugin_count": len(self._loaded),
            "active": sum(1 for lp in self._loaded if lp.active),
            "plugins": [
                {
                    "id": lp.spec.id,
                    "kind": lp.spec.kind,
                    "source": lp.spec.source,
                    "active": lp.active,
                    "health": lp.health,
                }
                for lp in self._loaded
            ],
        }
