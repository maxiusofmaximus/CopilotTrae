from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from local_ai_agent.contracts import InteractionLogSink
from local_ai_agent.log_safety import append_jsonl, redact_secrets


class InteractionLogger(InteractionLogSink):
    def __init__(
        self,
        logs_dir: Path | str,
        session_id: str,
        *,
        max_bytes: int = 1_048_576,
        max_backups: int = 3,
    ) -> None:
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.logs_dir / f"{session_id}.jsonl"
        self.max_bytes = max_bytes
        self.max_backups = max_backups

    def log_interaction(self, payload: dict[str, Any]) -> Path:
        entry = redact_secrets(
            {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": "interaction",
            **payload,
            }
        )
        return append_jsonl(
            self.log_path,
            entry,
            max_bytes=self.max_bytes,
            max_backups=self.max_backups,
        )
