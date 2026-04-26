from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from types import TracebackType
from typing import Any

from kvault_mcp.core.kernel import KernelCore


class TempVault:
    """Throwaway vault for integration tests.

    Usage:
        with TempVault() as vault:
            vault.write_file("AI/agents.md", "content")
            vault.set_config({"plugins": {"retriever": {"toy": {"active": True}}}})
            vault.install_plugin("retriever/toy", Path("tests/fixtures/toy_plugin"))
            kernel = vault.start_kernel()
    """

    def __init__(self) -> None:
        self._tmp: tempfile.TemporaryDirectory[str] | None = None
        self._root: Path | None = None
        self._config: dict[str, Any] = {}
        self._user_global: Path | None = None

    # ── Context manager ──────────────────────────────────────────────────

    def __enter__(self) -> TempVault:
        self._tmp = tempfile.TemporaryDirectory(prefix="kvault-test-")
        self._root = Path(self._tmp.name)
        (self._root / "kvault.config.toml").write_text("")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._tmp is not None:
            self._tmp.cleanup()
            self._tmp = None
            self._root = None

    # ── Inputs ───────────────────────────────────────────────────────────

    @property
    def root(self) -> Path:
        if self._root is None:
            raise RuntimeError("TempVault must be used as a context manager")
        return self._root

    def write_file(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def set_config(self, config: dict[str, Any]) -> None:
        self._config = _deep_merge(self._config, config)
        self._write_config_toml()

    def install_plugin(self, kind_name: str, source: Path) -> Path:
        if "/" not in kind_name:
            raise ValueError(f"install_plugin expects 'kind/name', got {kind_name!r}")
        dest = self.root / "kvault.plugins" / kind_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)
        return dest

    def set_user_global(self, path: Path) -> None:
        """Override the user-global plugin root (defaults to ~/.config/kvault/plugins)."""
        self._user_global = path

    # ── Output ───────────────────────────────────────────────────────────

    def start_kernel(self) -> KernelCore:
        kernel = KernelCore(
            vault_root=self.root,
            user_global_root=self._user_global,
        )
        kernel.start()
        return kernel

    # ── Internals ────────────────────────────────────────────────────────

    def _write_config_toml(self) -> None:
        (self.root / "kvault.config.toml").write_text(_to_toml(self._config))


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in overlay.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _is_bare_key(key: str) -> bool:
    """TOML unquoted keys are `[A-Za-z0-9_-]+` (spec §keys)."""
    if not key:
        return False
    return all(c.isalnum() or c in "_-" for c in key)


def _toml_key(key: str) -> str:
    """Emit a TOML key, quoting when the key contains non-bare characters."""
    if _is_bare_key(key):
        return key
    return '"' + key.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _is_dict_of_scalars(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return all(not isinstance(v, dict) for v in value.values())


def _to_toml(data: dict[str, Any], prefix: str = "") -> str:
    """Minimal TOML writer sufficient for kvault config files.

    Handles: nested `[kind.name]` tables, scalars, lists of scalars, and
    dict-of-scalars values (rendered as inline TOML tables so dotted keys —
    file paths — survive round-trip). Avoids the extra `tomli-w` dep.
    """
    lines: list[str] = []
    scalars: dict[str, Any] = {}
    sub_tables: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict) and not _is_dict_of_scalars(value):
            sub_tables[key] = value
        else:
            scalars[key] = value  # scalars, lists, AND dict-of-scalars inline tables

    if scalars:
        if prefix:
            lines.append(f"[{prefix}]")
        for key, value in scalars.items():
            lines.append(f"{_toml_key(key)} = {_toml_scalar(value)}")
        lines.append("")

    for key, subtable in sub_tables.items():
        new_prefix = f"{prefix}.{_toml_key(key)}" if prefix else _toml_key(key)
        lines.append(_to_toml(subtable, prefix=new_prefix))
    return "\n".join(lines)


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if value is None:
        return '""'
    if isinstance(value, list):
        return "[" + ", ".join(_toml_scalar(v) for v in value) + "]"
    if isinstance(value, dict):
        parts = [f"{_toml_key(k)} = {_toml_scalar(v)}" for k, v in value.items()]
        return "{ " + ", ".join(parts) + " }"
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'
