from __future__ import annotations

import json
from pathlib import Path

from local_ai_agent.contracts import MemoryStore
from local_ai_agent.models import ChatMessage


class _BaseConversationMemory(MemoryStore):
    def __init__(self, max_messages: int, system_prompt: str | None = None) -> None:
        self.max_messages = max_messages
        self.system_prompt = system_prompt
        self._messages: list[ChatMessage] = []

    def add(self, role: str, content: str) -> None:
        if role == "system":
            self.system_prompt = content
            return

        self._messages.append(ChatMessage(role=role, content=content))
        self._messages = self._messages[-self.max_messages :]
        self._after_add(self._messages[-1])

    def recent_messages(self) -> list[ChatMessage]:
        return list(self._messages)

    def build_request_messages(self, user_input: str) -> list[ChatMessage]:
        request_messages: list[ChatMessage] = []
        if self.system_prompt:
            request_messages.append(ChatMessage(role="system", content=self.system_prompt))
        request_messages.extend(self.recent_messages())
        request_messages.append(ChatMessage(role="user", content=user_input))
        return request_messages

    def _after_add(self, message: ChatMessage) -> None:
        return None


class ConversationMemory(_BaseConversationMemory):
    pass


class PersistentConversationMemory(_BaseConversationMemory):
    def __init__(self, max_messages: int, system_prompt: str | None, storage_path: str | Path) -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        super().__init__(max_messages=max_messages, system_prompt=system_prompt)
        self._load_existing_messages()

    def _load_existing_messages(self) -> None:
        if not self.storage_path.exists():
            return

        messages: list[ChatMessage] = []
        for line in self.storage_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            messages.append(ChatMessage.model_validate(payload))
        self._messages = messages[-self.max_messages :]

    def _after_add(self, message: ChatMessage) -> None:
        with self.storage_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(message.model_dump(), ensure_ascii=True) + "\n")
