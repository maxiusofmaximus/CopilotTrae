from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ModuleManifest:
    module_id: str
    module_type: str
    version: str
    enabled: bool
    capabilities: tuple[str, ...]

    def to_snapshot_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["capabilities"] = list(self.capabilities)
        return payload
