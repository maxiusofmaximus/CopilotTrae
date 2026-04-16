from __future__ import annotations

from pathlib import Path

from local_ai_agent.tools.contracts import ToolAdapterDescriptor, ToolSpec


class ToolRegistry:
    def __init__(self) -> None:
        self.version = "1"
        self._tools: list[ToolSpec] = []

    def register(
        self,
        *,
        tool_name: str,
        adapter: ToolAdapterDescriptor,
        binary_path: Path,
        aliases: list[str],
        capabilities: list[str],
        available: bool,
    ) -> None:
        self._tools.append(
            ToolSpec(
                tool_name=tool_name,
                adapter_name=adapter.adapter_name,
                shell=adapter.shell,
                binary_path=binary_path,
                aliases=tuple(aliases),
                capabilities=tuple(capabilities),
                available=available,
            )
        )

    def snapshot_tools(self) -> list[dict[str, object]]:
        return [
            tool.to_snapshot_dict()
            for tool in self._tools
            if tool.is_validated_available()
        ]
