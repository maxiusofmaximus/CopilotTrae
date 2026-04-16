from local_ai_agent.models import ChatMessage, ChatRequest


def test_chat_request_serializes_openai_style_messages():
    request = ChatRequest(
        model="llama-4-scout",
        messages=[
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="Hello"),
        ],
        temperature=0.2,
        max_tokens=256,
    )

    payload = request.to_payload()

    assert payload["model"] == "llama-4-scout"
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["content"] == "Hello"
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 256
