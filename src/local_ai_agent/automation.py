from __future__ import annotations

from typing import Protocol


class AutomationAdapter(Protocol):
    def send(self, text: str) -> None:
        ...


class NoopAutomationAdapter:
    def send(self, text: str) -> None:
        raise NotImplementedError("UI automation is intentionally not implemented in v1.")
