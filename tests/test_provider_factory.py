import pytest
import httpx

from local_ai_agent.config import Settings
from local_ai_agent.models import ChatMessage, ChatRequest
from local_ai_agent.providers import build_provider
from local_ai_agent.providers.fallback import FallbackLLMClient
from local_ai_agent.providers.base import ProviderTransportError
from local_ai_agent.providers.openai_compatible import GenericOpenAICompatibleClient
from local_ai_agent.providers.stub import StubClient
from local_ai_agent.providers.cerebras import CerebrasClient


def test_provider_factory_builds_cerebras_client():
    settings = Settings(
        provider="cerebras",
        api_key="test-key",
        base_url="https://api.cerebras.ai/v1",
        model="llama3.1-8b",
    )

    client = build_provider(settings)

    assert isinstance(client, CerebrasClient)
    assert client.provider_name == "cerebras"


def test_provider_factory_builds_stub_client():
    settings = Settings(
        provider="stub",
        model="stub-model",
        stub_response_text="stubbed reply",
    )

    client = build_provider(settings)

    assert isinstance(client, StubClient)
    assert client.provider_name == "stub"


def test_provider_factory_builds_openai_compatible_client():
    settings = Settings(
        provider="openai_compatible",
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-4o-mini",
    )

    client = build_provider(settings)

    assert isinstance(client, GenericOpenAICompatibleClient)
    assert client.provider_name == "openai_compatible"


def test_provider_factory_wraps_primary_with_fallback_client():
    settings = Settings(
        provider="failing-stub",
        fallback_provider="stub",
        model="stub-model",
        stub_response_text="fallback reply",
    )

    client = build_provider(settings)
    response = client.complete(
        ChatRequest(
            model="stub-model",
            messages=[ChatMessage(role="user", content="Hello")],
        )
    )

    assert isinstance(client, FallbackLLMClient)
    assert response.provider == "stub"
    assert response.content == "fallback reply"


def test_provider_factory_can_fallback_to_openai_compatible_client(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "openai/gpt-4o-mini",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Fallback real provider"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    real_http_client = httpx.Client(
        base_url="https://openrouter.ai/api/v1",
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(
        "local_ai_agent.providers.openai_compatible.httpx.Client",
        lambda **kwargs: real_http_client,
    )

    settings = Settings(
        provider="failing-stub",
        fallback_provider="openai_compatible",
        api_key="primary-key",
        base_url="https://api.cerebras.ai/v1",
        model="primary-model",
        fallback_api_key="fallback-key",
        fallback_base_url="https://openrouter.ai/api/v1",
        fallback_model="openai/gpt-4o-mini",
    )

    client = build_provider(settings)
    response = client.complete(
        ChatRequest(
            model="primary-model",
            messages=[ChatMessage(role="user", content="Hello")],
        )
    )

    assert isinstance(client, FallbackLLMClient)
    assert response.provider == "openai_compatible"
    assert response.model == "openai/gpt-4o-mini"
    assert response.content == "Fallback real provider"


def test_fallback_client_only_handles_provider_failures():
    class ProviderFailingClient:
        provider_name = "provider-failing"

        def complete(self, request: ChatRequest):
            raise ProviderTransportError("transport failure")

    class BusinessFailingClient:
        provider_name = "business-failing"

        def complete(self, request: ChatRequest):
            raise ValueError("business failure")

    request = ChatRequest(model="stub-model", messages=[ChatMessage(role="user", content="Hello")])
    fallback = StubClient(model="stub-model", response_text="fallback reply")

    provider_wrapped = FallbackLLMClient(primary=ProviderFailingClient(), fallback=fallback)
    response = provider_wrapped.complete(request)
    assert response.content == "fallback reply"

    business_wrapped = FallbackLLMClient(primary=BusinessFailingClient(), fallback=fallback)
    with pytest.raises(ValueError):
        business_wrapped.complete(request)
