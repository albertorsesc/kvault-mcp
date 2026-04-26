from __future__ import annotations

from conftest import TOY_PLUGIN

from kvault_mcp.testing import TempVault


def test_write_file_and_install_plugin_and_start_kernel() -> None:
    with TempVault() as vault:
        vault.write_file("AI/agents.md", "# agents\nhello\n")
        vault.install_plugin("retriever/toy", TOY_PLUGIN)
        vault.set_config({"plugins": {"retriever": {"toy": {"active": True}}}})

        kernel = vault.start_kernel()
        plugins = kernel.loaded_plugins()
        assert any(lp.spec.id == "retriever.toy" and lp.active for lp in plugins)


def test_inactive_plugin_not_instantiated() -> None:
    with TempVault() as vault:
        vault.install_plugin("retriever/toy", TOY_PLUGIN)
        vault.set_config({"plugins": {"retriever": {"toy": {"active": False}}}})

        kernel = vault.start_kernel()
        lp = kernel.plugin_by_id("retriever.toy")
        assert lp is not None
        assert lp.active is False
        assert lp.instance is None


def test_missing_config_toml_does_not_crash() -> None:
    # Entry-point-bundled plugins are discovered in every vault, but none is active
    # until the vault's config opts one in. An empty config means zero active plugins.
    with TempVault() as vault:
        kernel = vault.start_kernel()
        summary = kernel.health_summary()
        assert summary["active"] == 0
