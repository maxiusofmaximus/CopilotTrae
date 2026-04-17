from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Callable, Protocol

from local_ai_agent.log_safety import append_jsonl, redact_secrets
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
    max_bytes: int = 1_048_576
    max_backups: int = 3

    def emit(self, event: object) -> None:
        payload = redact_secrets(_event_payload(event))
        append_jsonl(
            self.log_path,
            payload,
            max_bytes=self.max_bytes,
            max_backups=self.max_backups,
        )


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
