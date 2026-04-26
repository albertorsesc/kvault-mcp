from __future__ import annotations

import sqlite3

import pytest
from conftest import PLUGIN_SOURCES

from kvault_mcp.kinds.vector_store import VectorStore
from kvault_mcp.testing import TempVault

pytest.importorskip("sqlite_vec")

if not hasattr(sqlite3.Connection, "enable_load_extension"):
    pytest.skip(
        "this Python lacks sqlite3 load_extension support",
        allow_module_level=True,
    )


def _start() -> tuple[TempVault, VectorStore]:
    vault = TempVault()
    vault.__enter__()
    vault.install_plugin("vector_store/sqlite_vec", PLUGIN_SOURCES["vector_store/sqlite_vec"])
    vault.set_config(
        {"plugins": {"vector_store": {"sqlite_vec": {"active": True}}}}
    )
    kernel = vault.start_kernel()
    store = kernel.get_active(VectorStore)
    assert store is not None
    return vault, store


def test_collection_create_list_and_query_roundtrip() -> None:
    vault, store = _start()
    try:
        store.collection_create("test_v1", 4)
        store.add(
            "test_v1",
            [
                {"id": "a", "embedding": [1.0, 0.0, 0.0, 0.0]},
                {"id": "b", "embedding": [0.0, 1.0, 0.0, 0.0]},
            ],
        )
        collections = store.collection_list()
        assert any(c["collection_id"] == "test_v1" and c["dimensions"] == 4 for c in collections)

        hits = store.query("test_v1", [1.0, 0.0, 0.0, 0.0], k=2)
        assert len(hits) == 2
        assert hits[0].id == "a"  # closest to query vector
    finally:
        vault.__exit__(None, None, None)


def test_dimension_mismatch_raises() -> None:
    vault, store = _start()
    try:
        store.collection_create("four_dim", 4)
        with pytest.raises(sqlite3.OperationalError):
            store.add("four_dim", [{"id": "x", "embedding": [0.1, 0.2, 0.3]}])  # 3 != 4
    finally:
        vault.__exit__(None, None, None)


def test_health_reports_vec_version() -> None:
    vault, store = _start()
    try:
        health = store.health()
        assert health["ok"] is True
        assert "sqlite_vec_version" in health
    finally:
        vault.__exit__(None, None, None)
