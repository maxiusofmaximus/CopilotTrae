from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from types import MappingProxyType

from local_ai_agent.modules.registry import ModuleRegistry
from local_ai_agent.router.snapshot import RegistrySnapshot
from local_ai_agent.tools.registry import ToolRegistry


def typed_empty_extensions() -> dict[str, object]:
    return {
        "aliases": MappingProxyType({}),
        "policies": MappingProxyType({}),
        "mcp_servers": (),
        "provider_status": MappingProxyType({}),
        "health_checks": (),
    }


def build_registry_snapshot(
    *,
    session_id: str,
    tool_registry: ToolRegistry,
    module_registry: ModuleRegistry,
) -> RegistrySnapshot:
    tools = tool_registry.snapshot_tools()
    modules = module_registry.snapshot_modules()
    extensions = typed_empty_extensions()
    snapshot_version = _stable_snapshot_version(
        session_id=session_id,
        tool_registry=tool_registry,
        module_registry=module_registry,
        tools=tools,
        modules=modules,
    )
    return RegistrySnapshot(
        snapshot_version=snapshot_version,
        built_at=datetime.now(timezone.utc).isoformat(),
        built_for_session=session_id,
        tools=tuple(tools),
        modules=tuple(modules),
        policies=extensions["policies"],
        source_versions={
            "tool_registry": tool_registry.version,
            "module_registry": module_registry.version,
        },
        execution_surface={"tools": tools},
        capability_surface=module_registry.snapshot_capabilities(),
        extensions=extensions,
    )


def _stable_snapshot_version(
    *,
    session_id: str,
    tool_registry: ToolRegistry,
    module_registry: ModuleRegistry,
    tools: list[dict[str, object]],
    modules: list[dict[str, object]],
) -> str:
    payload = {
        "session_id": session_id,
        "tool_registry_version": tool_registry.version,
        "module_registry_version": module_registry.version,
        "tools": tools,
        "modules": modules,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()
    return f"snap-{digest[:16]}"
