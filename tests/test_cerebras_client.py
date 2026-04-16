import json

import httpx

from local_ai_agent.models import ChatMessage, ChatRequest
from local_ai_agent.providers.cerebras import CerebrasClient


def test_cerebras_client_posts_openai_compatible_payload():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["auth"] = request.headers["Authorization"]
        captured["payload"] = request.content.decode("utf-8")
        return httpx.Response(
            200,
            json={
                "model": "gpt-oss-120b",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Ready."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
            },
        )

    http_client = httpx.Client(
        base_url="https://api.cerebras.ai/v1",
        transport=httpx.MockTransport(handler),
    )
    client = CerebrasClient(
        api_key="test-key",
        base_url="https://api.cerebras.ai/v1",
        timeout_seconds=5,
        max_retries=1,
        http_client=http_client,
    )

    response = client.complete(
        ChatRequest(
            model="gpt-oss-120b",
            messages=[ChatMessage(role="user", content="Hello")],
        )
    )

    assert captured["path"] == "/v1/chat/completions"
    assert captured["auth"] == "Bearer test-key"
    payload = json.loads(str(captured["payload"]))
    assert payload["messages"][0]["role"] == "user"
    assert response.content == "Ready."
    assert response.usage is not None
    assert response.usage.total_tokens == 14
