from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REDACTED = "[REDACTED]"
SECRET_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "bearer",
        "refresh_token",
        "token",
    }
)


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: REDACTED if isinstance(key, str) and key.lower() in SECRET_KEYS else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


def append_jsonl(path: Path, payload: dict[str, Any], *, max_bytes: int, max_backups: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=True) + "\n"
    encoded_size = len(serialized.encode("utf-8"))

    if max_bytes > 0 and path.exists() and path.stat().st_size + encoded_size > max_bytes:
        _rotate_jsonl(path, max_backups=max_backups)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(serialized)
    return path


def _rotate_jsonl(path: Path, *, max_backups: int) -> None:
    if not path.exists():
        return

    if max_backups <= 0:
        path.unlink()
        return

    oldest_backup = path.with_name(f"{path.name}.{max_backups}")
    if oldest_backup.exists():
        oldest_backup.unlink()

    for index in range(max_backups - 1, 0, -1):
        source = path.with_name(f"{path.name}.{index}")
        if source.exists():
            source.replace(path.with_name(f"{path.name}.{index + 1}"))

    path.replace(path.with_name(f"{path.name}.1"))
