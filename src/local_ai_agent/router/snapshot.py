from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


def _freeze_value(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class RegistrySnapshot:
    snapshot_version: str
    built_for_session: str
    built_at: str = ""
    tools: tuple[MappingProxyType, ...] = field(default_factory=tuple)
    modules: tuple[MappingProxyType, ...] = field(default_factory=tuple)
    policies: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))
    source_versions: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))
    execution_surface: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))
    capability_surface: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))
    extensions: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "tools", tuple(_freeze_value(tool) for tool in self.tools))
        object.__setattr__(self, "modules", tuple(_freeze_value(module) for module in self.modules))
        object.__setattr__(self, "policies", _freeze_value(dict(self.policies)))
        object.__setattr__(self, "source_versions", _freeze_value(dict(self.source_versions)))
        object.__setattr__(self, "execution_surface", _freeze_value(dict(self.execution_surface)))
        object.__setattr__(self, "capability_surface", _freeze_value(dict(self.capability_surface)))
        object.__setattr__(self, "extensions", _freeze_value(dict(self.extensions)))

    @classmethod
    def minimal(cls, *, snapshot_version: str, built_for_session: str) -> "RegistrySnapshot":
        return cls(snapshot_version=snapshot_version, built_for_session=built_for_session)
