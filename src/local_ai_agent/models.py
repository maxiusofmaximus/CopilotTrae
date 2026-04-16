from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

MessageRole = Literal["system", "user", "assistant", "developer"]


class ChatMessage(BaseModel):
    role: MessageRole
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float | None = Field(default=0.2)
    max_tokens: int | None = None
    stream: bool = False

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class TokenUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatResponse(BaseModel):
    provider: str
    model: str
    content: str
    finish_reason: str | None = None
    usage: TokenUsage | None = None
