from dataclasses import is_dataclass
from pathlib import Path

from local_ai_agent.tools.adapters.bash import BashToolAdapter
from local_ai_agent.tools.adapters.generic_cli import GenericCliToolAdapter
from local_ai_agent.tools.adapters.powershell import PowerShellToolAdapter
from local_ai_agent.tools.registry import ToolRegistry


def test_tool_registry_only_exports_validated_available_tools(tmp_path):
    available_binary = tmp_path / "gh.exe"
    available_binary.write_text("fake-binary", encoding="utf-8")

    registry = ToolRegistry()
    registry.register(
        tool_name="gh",
        adapter=GenericCliToolAdapter(shell="powershell"),
        binary_path=available_binary,
        aliases=["github", "github-cli"],
        capabilities=["version"],
        available=True,
    )
    registry.register(
        tool_name="missing",
        adapter=PowerShellToolAdapter(),
        binary_path=tmp_path / "missing.exe",
        aliases=["missing-cli"],
        capabilities=["version"],
        available=True,
    )

    snapshot_tools = registry.snapshot_tools()

    assert snapshot_tools[0]["tool_name"] == "gh"
    assert snapshot_tools[0]["available"] is True
    assert [tool["tool_name"] for tool in snapshot_tools] == ["gh"]


def test_tool_adapters_are_descriptors_and_not_executors():
    generic = GenericCliToolAdapter(shell="powershell")
    bash = BashToolAdapter()
    powershell = PowerShellToolAdapter()

    assert is_dataclass(generic)
    assert is_dataclass(bash)
    assert is_dataclass(powershell)
    assert not hasattr(generic, "run")
    assert not hasattr(bash, "run")
    assert not hasattr(powershell, "run")
