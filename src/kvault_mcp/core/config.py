from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, validators


def _extend_with_default(validator_class: type) -> type:
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):  # type: ignore[no-untyped-def]
        if isinstance(instance, dict):
            for prop, subschema in properties.items():
                if isinstance(subschema, dict) and "default" in subschema:
                    instance.setdefault(prop, subschema["default"])
        yield from validate_properties(validator, properties, instance, schema)

    return validators.extend(validator_class, {"properties": set_defaults})


DefaultFillingValidator = _extend_with_default(Draft202012Validator)


def _coerce_env_value(raw: str) -> Any:
    lowered = raw.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


class ConfigResolver:
    def __init__(
        self,
        vault_root: Path,
        env: dict[str, str] | None = None,
    ) -> None:
        self._vault_root = vault_root
        self._env = dict(os.environ if env is None else env)
        self._raw_toml: dict[str, Any] = self._load_toml()

    def _load_toml(self) -> dict[str, Any]:
        config_path = self._vault_root / "kvault.config.toml"
        if not config_path.exists():
            return {}
        with config_path.open("rb") as f:
            return tomllib.load(f)

    def kernel_section(self) -> dict[str, Any]:
        return dict(self._raw_toml.get("kernel", {}))

    def retrieval_section(self) -> dict[str, Any]:
        return dict(self._raw_toml.get("retrieval", {}))

    def resolve_plugin(
        self,
        plugin_id: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve config for `plugin_id` (format 'kind.name')."""
        kind, _, name = plugin_id.partition(".")
        if not kind or not name:
            raise ValueError(f"plugin_id must be 'kind.name', got {plugin_id!r}")

        toml_section: dict[str, Any] = (
            self._raw_toml.get("plugins", {}).get(kind, {}).get(name, {})
        )
        resolved: dict[str, Any] = dict(toml_section)

        env_prefix = f"KVAULT_{kind.upper()}_{name.upper()}_"
        for env_key, env_val in self._env.items():
            if not env_key.startswith(env_prefix):
                continue
            suffix = env_key[len(env_prefix):].lower().replace("__", ".")
            resolved[suffix] = _coerce_env_value(env_val)

        if schema is not None:
            errors = _validate_and_fill(schema, resolved)
            if errors:
                raise ValueError(
                    f"config invalid for {plugin_id}: {'; '.join(errors)}"
                )
        return resolved

    def raw(self) -> dict[str, Any]:
        return dict(self._raw_toml)


def _validate_and_fill(schema: dict[str, Any], config: dict[str, Any]) -> list[str]:
    validator = DefaultFillingValidator(schema)
    errors: list[str] = []
    for err in sorted(validator.iter_errors(config), key=lambda e: list(e.absolute_path)):
        path = "/".join(map(str, err.absolute_path)) or "<root>"
        errors.append(f"{path}: {err.message}")
    return errors
