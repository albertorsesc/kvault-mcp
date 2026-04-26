from __future__ import annotations

from conftest import TOY_PLUGIN

from kvault_mcp.kinds.retriever import Retriever
from kvault_mcp.testing import TempVault


def test_active_plugin_registers_against_its_provides_protocol() -> None:
    with TempVault() as vault:
        vault.install_plugin("retriever/toy", TOY_PLUGIN)
        vault.set_config({"plugins": {"retriever": {"toy": {"active": True}}}})

        kernel = vault.start_kernel()
        instance = kernel.get_active(Retriever)
        assert instance is not None
        result = instance.query("hello world")
        assert result[0]["snippet"].startswith("hello")


def test_state_path_from_kernel() -> None:
    with TempVault() as vault:
        kernel = vault.start_kernel()
        path = kernel.state_path("semantic", "vault-capabilities.jsonl")
        assert path.name == "vault-capabilities.jsonl"
        assert path.parent.exists()


def test_publish_reaches_plugin_event_consumer() -> None:
    with TempVault() as vault:
        vault.install_plugin("retriever/toy", TOY_PLUGIN)
        vault.set_config({"plugins": {"retriever": {"toy": {"active": True}}}})
        kernel = vault.start_kernel()
        kernel.publish("vault.toy.ping", {"n": 1})
        kernel.publish("vault.toy.ping", {"n": 2})

        toy = kernel.get_active(Retriever)
        assert toy.pings_received == 2  # type: ignore[attr-defined]


def test_health_summary_shape() -> None:
    with TempVault() as vault:
        vault.install_plugin("retriever/toy", TOY_PLUGIN)
        vault.set_config({"plugins": {"retriever": {"toy": {"active": True}}}})
        kernel = vault.start_kernel()
        summary = kernel.health_summary()
        # Only the toy is opted-in as active in this vault's config; the
        # entry-point bundled plugins are discovered but stay inactive.
        assert summary["active"] == 1
        assert any(p["id"] == "retriever.toy" and p["active"] for p in summary["plugins"])
