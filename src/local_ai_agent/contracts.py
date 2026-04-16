from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from local_ai_agent.models import ChatMessage


@runtime_checkable
class MemoryStore(Protocol):
    def add(self, role: str, content: str) -> None:
        ...

    def recent_messages(self) -> list[ChatMessage]:
        ...

    def build_request_messages(self, user_input: str) -> list[ChatMessage]:
        ...


@runtime_checkable
class InteractionLogSink(Protocol):
    def log_interaction(self, payload: dict[str, Any]) -> Path:
        ...


@runtime_checkable
class InputSource(Protocol):
    def read(self) -> str:
        ...


@runtime_checkable
class OutputSink(Protocol):
    def emit(self, text: str) -> None:
        ...


@runtime_checkable
class ConfirmationPolicy(Protocol):
    def confirm(self, prompt: str) -> bool:
        ...


@runtime_checkable
class ClipboardSink(Protocol):
    def copy(self, text: str) -> None:
        ...
