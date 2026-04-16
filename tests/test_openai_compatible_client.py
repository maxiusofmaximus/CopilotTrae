import json

import httpx

from local_ai_agent.models import ChatMessage, ChatRequest
from local_ai_agent.providers.openai_compatible import GenericOpenAICompatibleClient


def test_openai_compatible_client_posts_openai_style_payload():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["auth"] = request.headers["Authorization"]
        captured["payload"] = request.content.decode("utf-8")
        return httpx.Response(
            200,
            json={
                "model": "openai/gpt-4o-mini",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Ready."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 5,
                    "total_tokens": 16,
                },
            },
        )

    http_client = httpx.Client(
        base_url="https://openrouter.ai/api/v1",
        transport=httpx.MockTransport(handler),
    )
    client = GenericOpenAICompatibleClient(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        timeout_seconds=5,
        max_retries=1,
        model="openai/gpt-4o-mini",
        provider_name="openai_compatible",
        http_client=http_client,
    )

    response = client.complete(
        ChatRequest(
            model="openai/gpt-4o-mini",
            messages=[ChatMessage(role="user", content="Hello")],
        )
    )

    assert captured["path"] == "/api/v1/chat/completions"
    assert captured["auth"] == "Bearer test-key"
    payload = json.loads(str(captured["payload"]))
    assert payload["model"] == "openai/gpt-4o-mini"
    assert payload["messages"][0]["role"] == "user"
    assert response.provider == "openai_compatible"
    assert response.content == "Ready."
    assert response.usage is not None
    assert response.usage.total_tokens == 16
