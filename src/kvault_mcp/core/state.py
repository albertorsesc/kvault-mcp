from __future__ import annotations

from pathlib import Path

_CATEGORIES: dict[str, tuple[str, ...]] = {
    "episodic": ("memory", "episodic"),
    "semantic": ("memory", "semantic"),
    "working": ("memory", "working"),
    "personal": ("memory", "personal"),
    "rules.proposed": ("memory", "rules", "proposed"),
    "rules.active": ("memory", "rules", "active"),
    "rules.retired": ("memory", "rules", "retired"),
}


class PathEscape(ValueError):
    """Raised when a `name` argument to state_path resolves outside its category."""


class StatePathResolver:
    """Maps (category, name) → absolute path inside the vault.

    Hard guarantee: the returned path is always inside the category directory,
    which is always inside the vault root. A plugin that passes `..` or an
    absolute path gets `PathEscape` — never a resolved path pointing outside
    the vault. Plugins cannot use this API to read or write anywhere but their
    assigned category.
    """

    def __init__(self, vault_root: Path, create: bool = True) -> None:
        # Preserve vault_root as-is so return paths don't surprise callers by
        # following symlinks. Escape-check uses `resolve()` internally instead.
        self._vault_root = vault_root
        self._create = create

    def path(self, category: str, name: str | None = None) -> Path:
        parts = _CATEGORIES.get(category)
        if parts is None:
            raise KeyError(f"unknown state category: {category!r}")
        directory = self._vault_root.joinpath(*parts)
        if self._create:
            directory.mkdir(parents=True, exist_ok=True)
        if name is None:
            return directory
        self._reject_unsafe_name(name)
        candidate = directory / name
        # Resolve on both sides to handle symlinks uniformly before the escape check.
        directory_resolved = directory.resolve()
        candidate_resolved = candidate.resolve()
        if (
            directory_resolved not in candidate_resolved.parents
            and candidate_resolved != directory_resolved
        ):
            raise PathEscape(
                f"name={name!r} resolves outside category {category!r}"
            )
        if self._create:
            candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate

    @staticmethod
    def _reject_unsafe_name(name: str) -> None:
        if not name:
            raise PathEscape("name must not be empty")
        if Path(name).is_absolute():
            raise PathEscape(f"name must be relative, got {name!r}")
        # Walk each part; '..' or absolute-root parts are a hard no.
        for part in Path(name).parts:
            if part in ("..", "/", "\\"):
                raise PathEscape(f"name must not contain traversal parts, got {name!r}")

    @staticmethod
    def categories() -> list[str]:
        return list(_CATEGORIES.keys())
