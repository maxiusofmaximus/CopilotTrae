from __future__ import annotations

from local_ai_agent.modules.manifest import ModuleManifest


class ModuleRegistry:
    def __init__(self) -> None:
        self.version = "1"
        self._modules: list[ModuleManifest] = []

    def register(self, manifest: ModuleManifest) -> None:
        self._modules.append(manifest)

    def snapshot_modules(self) -> list[dict[str, object]]:
        return [manifest.to_snapshot_dict() for manifest in self._modules if manifest.enabled]

    def snapshot_capabilities(self) -> dict[str, tuple[str, ...]]:
        capabilities = {
            capability
            for manifest in self._modules
            if manifest.enabled
            for capability in manifest.capabilities
        }
        return {"capabilities": tuple(sorted(capabilities))}
