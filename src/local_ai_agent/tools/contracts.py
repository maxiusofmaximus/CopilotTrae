from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


class ToolAdapterDescriptor(Protocol):
    adapter_name: str
    shell: str


@dataclass(frozen=True, slots=True)
class ToolSpec:
    tool_name: str
    adapter_name: str
    shell: str
    binary_path: Path
    aliases: tuple[str, ...]
    capabilities: tuple[str, ...]
    available: bool

    def is_validated_available(self) -> bool:
        return self.available and self.binary_path.exists()

    def to_snapshot_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["binary_path"] = str(self.binary_path)
        payload["aliases"] = list(self.aliases)
        payload["capabilities"] = list(self.capabilities)
        payload["available"] = self.is_validated_available()
        return payload
