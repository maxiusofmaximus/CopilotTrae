from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from local_ai_agent.contracts import InteractionLogSink


class InteractionLogger(InteractionLogSink):
    def __init__(self, logs_dir: Path | str, session_id: str) -> None:
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.logs_dir / f"{session_id}.jsonl"

    def log_interaction(self, payload: dict[str, Any]) -> Path:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": "interaction",
            **payload,
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
        return self.log_path
