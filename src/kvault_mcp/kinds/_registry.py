from __future__ import annotations

PROVIDER_TYPES: dict[str, type] = {}


def register_provider_type(name: str, protocol: type) -> None:
    """Map a `provides`-string (from plugin.toml) to a Protocol class.

    Called from each kind module's top-level to register itself. Third-party
    packages that introduce a new kind register here on import. The kernel reads
    this registry without knowing the set of kinds at import time.
    """
    existing = PROVIDER_TYPES.get(name)
    if existing is not None and existing is not protocol:
        raise ValueError(
            f"provider type {name!r} already registered to a different protocol "
            f"({existing!r} vs {protocol!r})"
        )
    PROVIDER_TYPES[name] = protocol
