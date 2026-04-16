from __future__ import annotations

from typing import Protocol

from local_ai_agent.models import ChatRequest, ChatResponse


class ProviderError(RuntimeError):
    pass


class ProviderConfigError(ProviderError):
    pass


class ProviderTransportError(ProviderError):
    pass


class ProviderResponseError(ProviderError):
    pass


class LLMClient(Protocol):
    provider_name: str

    def complete(self, request: ChatRequest) -> ChatResponse:
        ...
