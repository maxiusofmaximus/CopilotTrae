from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class RouterRequestReceived:
    request_id: str
    session_id: str
    request_snapshot_version: str
    shell: str
    raw_input: str

    @property
    def event_name(self) -> str:
        return "router.request_received"


@dataclass(frozen=True, slots=True)
class RouterSnapshotBound:
    request_id: str
    session_id: str
    snapshot_version: str

    @property
    def event_name(self) -> str:
        return "router.snapshot_bound"


@dataclass(frozen=True, slots=True)
class RouterIntentClassified:
    request_id: str
    session_id: str
    snapshot_version: str
    intent: str

    @property
    def event_name(self) -> str:
        return "router.intent_classified"


@dataclass(frozen=True, slots=True)
class RouterRouteEmitted:
    request_id: str
    session_id: str
    snapshot_version: str
    route: str
    intent: str

    @property
    def event_name(self) -> str:
        return "router.route_emitted"


@dataclass(frozen=True, slots=True)
class RouterErrorEmitted:
    request_id: str
    session_id: str
    snapshot_version: str
    error_code: str
    diagnostics: Mapping[str, object]

    @property
    def event_name(self) -> str:
        return "router.error_emitted"
