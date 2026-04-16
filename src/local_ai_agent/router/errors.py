from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from local_ai_agent.router.output import EnvelopeMetadata


@dataclass(frozen=True, slots=True)
class RouterErrorEnvelope:
    error_code: str
    request_id: str
    session_id: str
    envelope: EnvelopeMetadata
    diagnostics: MappingProxyType

    def __init__(
        self,
        *,
        error_code: str,
        request_id: str,
        session_id: str,
        snapshot_version: str,
        diagnostics: dict[str, Any],
    ) -> None:
        object.__setattr__(self, "error_code", error_code)
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(
            self,
            "envelope",
            EnvelopeMetadata(kind="router_error", snapshot_version=snapshot_version),
        )
        object.__setattr__(self, "diagnostics", MappingProxyType(dict(diagnostics)))

    @property
    def kind(self) -> str:
        return self.envelope.kind

    @property
    def snapshot_version(self) -> str:
        return self.envelope.snapshot_version
