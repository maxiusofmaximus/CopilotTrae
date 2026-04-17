from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Callable, Protocol

from local_ai_agent.router.snapshot import RegistrySnapshot


class SnapshotProvider(Protocol):
    def get_snapshot(self, session_id: str) -> RegistrySnapshot:
        ...


@dataclass(slots=True)
class CachedSnapshotProvider:
    snapshot_factory: Callable[[str], RegistrySnapshot]
    _snapshots: dict[str, RegistrySnapshot] = field(default_factory=dict)

    def get_snapshot(self, session_id: str) -> RegistrySnapshot:
        snapshot = self._snapshots.get(session_id)
        if snapshot is None:
            snapshot = self.snapshot_factory(session_id)
            self._snapshots[session_id] = snapshot
        return snapshot


@dataclass(slots=True)
class JsonlRouterEventSink:
    log_path: Path

    def emit(self, event: object) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = _event_payload(event)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _event_payload(event: object) -> dict[str, object]:
    if is_dataclass(event):
        payload = dict(asdict(event))
    elif isinstance(event, dict):
        payload = dict(event)
    else:
        payload = {"value": repr(event)}

    event_name = getattr(event, "event_name", None)
    if isinstance(event_name, str):
        payload["event_name"] = event_name
    return payload
