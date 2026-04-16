from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


def _default_env_visible() -> dict[str, str]:
    return {}


@dataclass(slots=True)
class TerminalRequest:
    request_id: str
    session_id: str
    shell: Literal["powershell", "bash"]
    raw_input: str
    cwd: str
    snapshot_version: str
    env_visible: dict[str, str] = field(default_factory=_default_env_visible)
    recent_history: list[str] = field(default_factory=list)
    ui_context: dict[str, str] = field(default_factory=dict)
    requested_mode: Literal["strict", "interactive", "headless"] = "strict"
