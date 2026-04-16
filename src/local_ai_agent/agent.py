from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from local_ai_agent.config import Settings
from local_ai_agent.contracts import InteractionLogSink, MemoryStore
from local_ai_agent.models import ChatMessage, ChatRequest
from local_ai_agent.providers.base import LLMClient


@dataclass(slots=True)
class AgentResult:
    normalized_input: str
    response_text: str
    memory_snapshot: list[ChatMessage]
    log_path: Path | None


def normalize_text(raw_text: str) -> str:
    normalized_lines = [line.rstrip() for line in raw_text.replace("\r\n", "\n").split("\n")]
    normalized = "\n".join(normalized_lines).strip()
    if not normalized:
        raise ValueError("Input is empty after normalization.")
    return normalized


class AgentController:
    def __init__(
        self,
        settings: Settings,
        llm_client: LLMClient,
        memory: MemoryStore,
        logger: InteractionLogSink,
    ) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self.memory = memory
        self.logger = logger

    def run_once(self, raw_text: str) -> AgentResult:
        normalized_input = normalize_text(raw_text)
        request = ChatRequest(
            model=self.settings.model,
            messages=self.memory.build_request_messages(normalized_input),
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )
        response = self.llm_client.complete(request)

        self.memory.add(role="user", content=normalized_input)
        self.memory.add(role="assistant", content=response.content)
        log_path = self.logger.log_interaction(
            {
                "provider": getattr(self.llm_client, "provider_name", self.settings.provider),
                "model": response.model or self.settings.model,
                "request": {"input": normalized_input, "messages": [message.model_dump() for message in request.messages]},
                "response": {
                    "content": response.content,
                    "finish_reason": response.finish_reason,
                    "usage": response.usage.model_dump(exclude_none=True) if response.usage else None,
                },
            }
        )

        return AgentResult(
            normalized_input=normalized_input,
            response_text=response.content,
            memory_snapshot=self.memory.recent_messages(),
            log_path=log_path,
        )
