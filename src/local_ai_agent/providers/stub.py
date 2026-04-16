from __future__ import annotations

from local_ai_agent.models import ChatRequest, ChatResponse
from local_ai_agent.providers.base import ProviderTransportError


class StubClient:
    provider_name = "stub"

    def __init__(self, model: str, response_text: str) -> None:
        self.model = model
        self.response_text = response_text

    def complete(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            provider=self.provider_name,
            model=request.model or self.model,
            content=self.response_text,
            finish_reason="stop",
        )


class FailingStubClient:
    provider_name = "failing-stub"

    def complete(self, request: ChatRequest) -> ChatResponse:
        raise ProviderTransportError("Stub transport failure")
