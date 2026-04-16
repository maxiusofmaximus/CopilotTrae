from __future__ import annotations

from local_ai_agent.config import Settings
from local_ai_agent.providers.base import LLMClient, ProviderConfigError
from local_ai_agent.providers.cerebras import CerebrasClient
from local_ai_agent.providers.fallback import FallbackLLMClient
from local_ai_agent.providers.openai_compatible import GenericOpenAICompatibleClient
from local_ai_agent.providers.stub import FailingStubClient, StubClient


def build_provider(settings: Settings) -> LLMClient:
    primary = _build_single_provider(settings.provider, settings, use_fallback_settings=False)
    if settings.fallback_provider:
        fallback = _build_single_provider(settings.fallback_provider, settings, use_fallback_settings=True)
        return FallbackLLMClient(primary=primary, fallback=fallback)
    return primary


def _build_single_provider(provider_name: str, settings: Settings, use_fallback_settings: bool) -> LLMClient:
    provider_name = provider_name.lower()
    api_key = settings.fallback_api_key if use_fallback_settings and settings.fallback_api_key else settings.api_key
    base_url = settings.fallback_base_url if use_fallback_settings and settings.fallback_base_url else settings.base_url
    model = settings.fallback_model if use_fallback_settings and settings.fallback_model else settings.model

    if provider_name == "cerebras":
        return CerebrasClient(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )
    if provider_name == "openai_compatible":
        return GenericOpenAICompatibleClient(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=settings.timeout_seconds,
            max_retries=settings.max_retries,
            model=model,
        )
    if provider_name == "stub":
        return StubClient(model=settings.model, response_text=settings.stub_response_text)
    if provider_name == "failing-stub":
        return FailingStubClient()

    raise ProviderConfigError(f"Unsupported provider: {provider_name}")
