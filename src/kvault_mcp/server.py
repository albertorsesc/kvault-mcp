from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.providers import Provider
from fastmcp.tools import Tool

from kvault_mcp import __version__
from kvault_mcp.core.kernel import KernelCore
from kvault_mcp.core.secrets import redact_config


class KvaultPluginProvider(Provider):
    """Sources MCP tools from the kernel's loaded plugins.

    A plugin declares tools in plugin.toml under `[tools.<tool_name>]`:

        [tools.my_tool]
        method = "handler_method"      # required; instance method to call
        description = "..."            # optional; defaults to f"{plugin.id}.{tool_name}"
        input_schema = "schemas/foo.json"  # optional; relative to plugin dir

    Tool names exposed to MCP clients are prefixed: `<kind>_<name>_<tool_name>`.
    """

    def __init__(self, kernel: KernelCore) -> None:
        super().__init__()
        self._kernel = kernel
        self._cache: dict[str, Tool] | None = None

    def _tools_by_name(self) -> dict[str, Tool]:
        # Cache the Tool objects so list and get return the same instances.
        # Rebuilding per call created fresh Tool objects whose Pydantic
        # introspection wasn't consistent with the `call_tool` resolver path,
        # producing "Unknown tool" on lookup despite visible-in-list.
        if self._cache is None:
            built: dict[str, Tool] = {}
            for t in [*self._kernel_tools(), *self._plugin_tools()]:
                built[t.name] = t
            self._cache = built
        return self._cache

    async def _list_tools(self, *args: Any, **kwargs: Any) -> Sequence[Tool]:
        return list(self._tools_by_name().values())

    async def _get_tool(self, name: str, *args: Any, **kwargs: Any) -> Tool | None:
        # FastMCP passes additional positional args (e.g. a request context) that
        # we don't currently use. Accepting *args keeps us forward-compatible
        # across FastMCP 3.x minor versions that add hooks here.
        return self._tools_by_name().get(name)

    def _kernel_tools(self) -> list[Tool]:
        kernel = self._kernel

        async def kvault_plugin_list() -> list[dict[str, Any]]:
            """List all discovered plugins with source, active state, and health."""
            return [
                {
                    "id": lp.spec.id,
                    "kind": lp.spec.kind,
                    "name": lp.spec.name,
                    "version": lp.spec.version,
                    "source": lp.spec.source,
                    "active": lp.active,
                    "health": lp.health,
                }
                for lp in kernel.loaded_plugins()
            ]

        async def kvault_config_show() -> dict[str, dict[str, Any]]:
            """Show resolved per-plugin config, with secrets redacted."""
            return {
                lp.spec.id: redact_config(kernel.config(lp.spec.id))
                for lp in kernel.loaded_plugins()
            }

        async def kvault_state_path(category: str, name: str | None = None) -> str:
            """Return the absolute path for a state category."""
            return str(kernel.state_path(category, name))

        async def kvault_health() -> dict[str, Any]:
            """Full kernel + plugin health summary."""
            return kernel.health_summary()

        return [
            Tool.from_function(kvault_plugin_list),
            Tool.from_function(kvault_config_show),
            Tool.from_function(kvault_state_path),
            Tool.from_function(kvault_health),
        ]

    def _plugin_tools(self) -> list[Tool]:
        """Build one FastMCP Tool per plugin-declared [tools.*] entry.

        `Tool.from_function` introspects the bound method's annotations to build
        the input schema and handles sync+async callables uniformly. No manual
        wrapping or signature patching — signatures are the source of truth.
        Plugins that want custom schemas declare them via pydantic / annotations
        on the method, not via separate schema files.
        """
        tools: list[Tool] = []
        for lp in self._kernel.loaded_plugins():
            if lp.instance is None or not lp.active:
                continue
            for tool_name, tool_meta in lp.spec.tools.items():
                method_name = tool_meta.get("method", tool_name)
                method = getattr(lp.instance, method_name, None)
                if method is None:
                    continue
                prefixed = f"{lp.spec.kind}_{lp.spec.name}_{tool_name}"
                description = str(
                    tool_meta.get("description", f"{lp.spec.id}.{tool_name}")
                )
                try:
                    tools.append(
                        Tool.from_function(method, name=prefixed, description=description)
                    )
                except Exception:
                    self._kernel.logger(lp.spec.id).exception(
                        "failed to register plugin tool; skipping",
                        extra={"event": "server.tool_registration_failed", "tool_id": prefixed},
                    )
        return tools


def build_server(kernel: KernelCore) -> FastMCP:
    return FastMCP(
        "kvault",
        version=__version__,
        providers=[KvaultPluginProvider(kernel)],
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="kvault-mcp")
    parser.add_argument(
        "--vault",
        default=os.environ.get("KVAULT_VAULT", ""),
        help="Absolute path to the vault (or set $KVAULT_VAULT).",
    )
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio"],
        help="Transport (stdio only for now).",
    )
    args = parser.parse_args()
    if not args.vault:
        raise SystemExit("--vault or $KVAULT_VAULT is required")
    vault_root = Path(args.vault).expanduser().resolve()
    if not vault_root.exists():
        raise SystemExit(f"vault does not exist: {vault_root}")

    kernel = KernelCore(vault_root=vault_root)
    kernel.start()
    server = build_server(kernel)
    asyncio.run(server.run_async(transport=args.transport))


if __name__ == "__main__":
    main()
