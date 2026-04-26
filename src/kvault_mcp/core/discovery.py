from __future__ import annotations

import importlib
import tomllib
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

from kvault_mcp.core.logger import make_logger

_log = make_logger("kernel.discovery")


@dataclass
class DiscoveredPlugin:
    id: str  # "kind.name"
    kind: str
    name: str
    version: str
    protocol_version: str
    source_path: Path
    source: str  # "vault_local" | "user_global" | "entry_point"
    plugin_dir: Path
    entrypoint: str
    module: str
    provides: list[str]
    consumes_events: list[str]
    emits_events: list[str]
    config_schema_path: Path | None
    install_required: list[str]
    tools: dict[str, dict[str, Any]] = field(default_factory=dict)
    shadows: list[str] = field(default_factory=list)

    @property
    def entry_point_spec(self) -> str | None:
        if self.source != "entry_point":
            return None
        return f"{self.module}:{self.entrypoint}"


def _safe_parse_plugin_toml(path: Path) -> dict[str, Any] | None:
    """Parse plugin.toml. A broken file is a discovery-time skip, not a kernel crash.

    Third-party plugins must never be able to take down the kernel by shipping a
    malformed manifest. Log the failure as a structured finding so operators can
    see which plugin needs attention.
    """
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        _log.warning(
            "skipped plugin with invalid manifest",
            extra={
                "event": "discovery.invalid_manifest",
                "plugin_id": str(path),
            },
        )
        _log.debug(
            "manifest parse error detail",
            extra={"event": "discovery.invalid_manifest_detail", "plugin_id": f"{path}: {exc}"},
        )
        return None


def _build_from_meta(
    meta: dict[str, Any],
    plugin_dir: Path,
    kind: str,
    name: str,
    source: str,
    source_path: Path,
    entrypoint: str,
    module: str,
) -> DiscoveredPlugin:
    schema_path: Path | None = None
    if meta.get("config_schema"):
        cand = plugin_dir / str(meta["config_schema"])
        if cand.exists():
            schema_path = cand
    return DiscoveredPlugin(
        id=f"{kind}.{name}",
        kind=kind,
        name=name,
        version=str(meta.get("version", "0.0.0")),
        protocol_version=str(meta.get("protocol_version", "1.0")),
        source_path=source_path,
        source=source,
        plugin_dir=plugin_dir,
        entrypoint=entrypoint,
        module=module,
        provides=list(meta.get("provides", [])),
        consumes_events=list(meta.get("consumes_events", [])),
        emits_events=list(meta.get("emits_events", [])),
        config_schema_path=schema_path,
        install_required=list(meta.get("install_required", [])),
        tools=dict(meta.get("tools", {})),
    )


def _make_plugin_from_toml(
    plugin_toml: Path,
    source: str,
) -> DiscoveredPlugin | None:
    """Build a DiscoveredPlugin from a plugin.toml path.

    `kind` and `id` come from the manifest (authoritative), matching the
    entry-point discovery path. Filesystem layout is organizational — a
    plugin.toml at any depth under `<vault>/kvault.plugins/` is valid so
    long as the manifest declares both fields.
    """
    meta = _safe_parse_plugin_toml(plugin_toml)
    if meta is None:
        return None
    kind = str(meta.get("kind", "")).strip()
    name = str(meta.get("id", "")).strip()
    if not kind or not name:
        _log.warning(
            "skipped plugin with missing kind or id",
            extra={
                "event": "discovery.incomplete_manifest",
                "plugin_id": str(plugin_toml),
            },
        )
        return None
    return _build_from_meta(
        meta=meta,
        plugin_dir=plugin_toml.parent,
        kind=kind,
        name=name,
        source=source,
        source_path=plugin_toml,
        entrypoint=str(meta.get("entrypoint", "")),
        module=str(meta.get("module", "handler")),
    )


def _scan_directory(root: Path, source: str) -> list[DiscoveredPlugin]:
    """Walk `root` recursively; any `plugin.toml` becomes a plugin candidate.

    Supports arbitrary grouping depth under `kvault.plugins/` — e.g.
    `kvault.plugins/rules/store/markdown/plugin.toml`. Once a plugin.toml is
    found at a given directory, subdirectories of THAT plugin aren't
    re-scanned (plugins don't contain plugins).
    """
    found: list[DiscoveredPlugin] = []
    if not root.exists() or not root.is_dir():
        return found
    seen_plugin_dirs: list[Path] = []
    for plugin_toml in sorted(root.rglob("plugin.toml")):
        plugin_dir = plugin_toml.parent
        if any(
            plugin_dir == pd or pd in plugin_dir.parents for pd in seen_plugin_dirs
        ):
            continue  # nested under an already-claimed plugin dir
        try:
            plugin = _make_plugin_from_toml(plugin_toml, source)
        except Exception:
            _log.exception(
                "skipped plugin due to unexpected discovery error",
                extra={
                    "event": "discovery.unexpected_error",
                    "plugin_id": str(plugin_toml),
                },
            )
            continue
        if plugin is not None:
            found.append(plugin)
            seen_plugin_dirs.append(plugin_dir)
    return found


def _discover_entry_points() -> list[DiscoveredPlugin]:
    out: list[DiscoveredPlugin] = []
    eps = entry_points(group="kvault.plugins")
    for ep in eps:
        try:
            cls = ep.load()
        except Exception:
            _log.warning(
                "skipped entry-point plugin that failed to load",
                extra={"event": "discovery.entry_point_load_failed", "plugin_id": ep.name},
            )
            continue
        module = importlib.import_module(cls.__module__)
        module_file = getattr(module, "__file__", None)
        if module_file is None:
            continue
        plugin_dir = Path(module_file).parent
        plugin_toml = plugin_dir / "plugin.toml"
        if not plugin_toml.exists():
            continue
        meta = _safe_parse_plugin_toml(plugin_toml)
        if meta is None:
            continue
        kind = str(meta.get("kind", ""))
        name = str(meta.get("id", ep.name))
        out.append(
            _build_from_meta(
                meta=meta,
                plugin_dir=plugin_dir,
                kind=kind,
                name=name,
                source="entry_point",
                source_path=plugin_toml,
                entrypoint=cls.__name__,
                module=cls.__module__,
            )
        )
    return out


def discover_plugins(
    vault_root: Path,
    user_global_root: Path | None = None,
) -> list[DiscoveredPlugin]:
    """Discover plugins across all three paths.

    Precedence on (kind, name) collision: vault-local > user-global > entry-point.
    Shadowed duplicates are logged and excluded. Malformed plugins are skipped
    (logged as findings) rather than crashing discovery.
    """
    candidates: list[DiscoveredPlugin] = []
    candidates.extend(_discover_entry_points())
    candidates.extend(
        _scan_directory(
            user_global_root or (Path.home() / ".config" / "kvault" / "plugins"),
            source="user_global",
        )
    )
    candidates.extend(
        _scan_directory(vault_root / "kvault.plugins", source="vault_local")
    )

    precedence = {"entry_point": 0, "user_global": 1, "vault_local": 2}
    winners: dict[str, DiscoveredPlugin] = {}
    for plugin in candidates:
        prev = winners.get(plugin.id)
        if prev is None:
            winners[plugin.id] = plugin
            continue
        if precedence[plugin.source] > precedence[prev.source]:
            plugin.shadows = list(prev.shadows) + [prev.source]
            winners[plugin.id] = plugin
            _log.warning(
                "plugin shadowed",
                extra={
                    "event": "discovery.shadowed",
                    "plugin_id": plugin.id,
                    "count": 1,
                },
            )
            _log.info(
                "shadow detail",
                extra={
                    "event": "discovery.shadow_detail",
                    "plugin_id": (
                        f"winner={plugin.source}:{plugin.source_path} "
                        f"shadowed={prev.source}:{prev.source_path}"
                    ),
                },
            )
        else:
            prev.shadows.append(plugin.source)
            _log.warning(
                "plugin shadowed",
                extra={
                    "event": "discovery.shadowed",
                    "plugin_id": plugin.id,
                    "count": 1,
                },
            )
            _log.info(
                "shadow detail",
                extra={
                    "event": "discovery.shadow_detail",
                    "plugin_id": (
                        f"winner={prev.source}:{prev.source_path} "
                        f"shadowed={plugin.source}:{plugin.source_path}"
                    ),
                },
            )
    return sorted(winners.values(), key=lambda p: p.id)
