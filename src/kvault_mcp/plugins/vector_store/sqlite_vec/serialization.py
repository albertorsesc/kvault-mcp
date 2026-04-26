from __future__ import annotations

import struct


def serialize_float32(vec: list[float]) -> bytes:
    """Pack a list of floats into the raw float32 byte layout sqlite-vec expects."""
    return struct.pack(f"{len(vec)}f", *vec)


def safe_identifier(raw: str) -> str:
    """Conservative SQLite identifier sanitizer for dynamic table names.

    Only [A-Za-z0-9_] allowed, never starting with a digit. Used to build
    per-collection `vec_<collection_id>` table names from user-supplied IDs.
    """
    out = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in raw)
    if not out or not (out[0].isalpha() or out[0] == "_"):
        out = "c_" + out
    return out
