from __future__ import annotations

from local_ai_agent.models import ChatRequest, ChatResponse
from local_ai_agent.providers.base import LLMClient, ProviderResponseError, ProviderTransportError


class FallbackLLMClient:
    def __init__(self, primary: LLMClient, fallback: LLMClient) -> None:
        self.primary = primary
        self.fallback = fallback
        self.provider_name = getattr(primary, "provider_name", "unknown")

    def complete(self, request: ChatRequest) -> ChatResponse:
        try:
            response = self.primary.complete(request)
            self.provider_name = getattr(self.primary, "provider_name", self.provider_name)
            return response
        except (ProviderTransportError, ProviderResponseError):
            response = self.fallback.complete(request)
            self.provider_name = getattr(self.fallback, "provider_name", self.provider_name)
            return response
