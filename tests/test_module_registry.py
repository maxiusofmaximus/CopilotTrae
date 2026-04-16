from types import MappingProxyType

from local_ai_agent.modules.manifest import ModuleManifest
from local_ai_agent.modules.registry import ModuleRegistry
from local_ai_agent.modules.snapshot_builder import build_registry_snapshot, typed_empty_extensions
from local_ai_agent.tools.adapters.generic_cli import GenericCliToolAdapter
from local_ai_agent.tools.registry import ToolRegistry


def test_snapshot_builder_materializes_tools_modules_and_typed_extensions(tmp_path):
    available_binary = tmp_path / "gh.exe"
    available_binary.write_text("fake-binary", encoding="utf-8")

    module_registry = ModuleRegistry()
    tool_registry = ToolRegistry()
    module_registry.register(
        ModuleManifest(
            module_id="mcp-context7",
            module_type="adapter",
            version="1.0.0",
            enabled=True,
            capabilities=("docs_lookup",),
        )
    )
    tool_registry.register(
        tool_name="gh",
        adapter=GenericCliToolAdapter(shell="powershell"),
        binary_path=available_binary,
        aliases=["github"],
        capabilities=["version"],
        available=True,
    )
    tool_registry.register(
        tool_name="ghost",
        adapter=GenericCliToolAdapter(shell="powershell"),
        binary_path=tmp_path / "ghost.exe",
        aliases=["ghost-cli"],
        capabilities=["version"],
        available=True,
    )

    snapshot = build_registry_snapshot(
        session_id="sess-1",
        tool_registry=tool_registry,
        module_registry=module_registry,
    )

    assert snapshot.built_for_session == "sess-1"
    assert set(snapshot.extensions.keys()) == {
        "aliases",
        "policies",
        "mcp_servers",
        "provider_status",
        "health_checks",
    }
    assert isinstance(snapshot.extensions["aliases"], MappingProxyType)
    assert isinstance(snapshot.extensions["mcp_servers"], tuple)
    assert snapshot.execution_surface["tools"][0]["tool_name"] == "gh"
    assert [tool["tool_name"] for tool in snapshot.execution_surface["tools"]] == ["gh"]
    assert "docs_lookup" in snapshot.capability_surface["capabilities"]


def test_typed_empty_extensions_returns_exact_required_keys():
    extensions = typed_empty_extensions()

    assert set(extensions.keys()) == {
        "aliases",
        "policies",
        "mcp_servers",
        "provider_status",
        "health_checks",
    }
