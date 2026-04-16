import json
from typing import get_type_hints

from local_ai_agent.agent import AgentController
from local_ai_agent.contracts import InteractionLogSink, MemoryStore
from local_ai_agent.config import Settings
from local_ai_agent.logging_utils import InteractionLogger
from local_ai_agent.memory import ConversationMemory
from local_ai_agent.models import ChatMessage, ChatRequest, ChatResponse
from local_ai_agent.providers.stub import StubClient


class FakeLLMClient:
    provider_name = "fake"

    def __init__(self) -> None:
        self.requests: list[ChatRequest] = []

    def complete(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        return ChatResponse(
            provider=self.provider_name,
            model=request.model,
            content="Structured answer",
            finish_reason="stop",
        )


class FakeMemoryStore:
    def __init__(self) -> None:
        self.messages: list[ChatMessage] = []

    def add(self, role: str, content: str) -> None:
        self.messages.append(ChatMessage(role=role, content=content))

    def recent_messages(self) -> list[ChatMessage]:
        return list(self.messages)

    def build_request_messages(self, user_input: str) -> list[ChatMessage]:
        return [ChatMessage(role="user", content=user_input)]


class FakeLogSink:
    def __init__(self, path) -> None:
        self.path = path
        self.entries: list[dict] = []

    def log_interaction(self, payload: dict) -> object:
        self.entries.append(payload)
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        return self.path


def test_agent_runs_deterministic_pipeline_and_logs_interaction(tmp_path):
    client = FakeLLMClient()
    settings = Settings(
        provider="cerebras",
        api_key="test-key",
        base_url="https://api.cerebras.ai/v1",
        model="llama3.1-8b",
        system_prompt="Be precise.",
        logs_dir=tmp_path,
        max_memory_messages=4,
    )
    memory = ConversationMemory(
        max_messages=settings.max_memory_messages,
        system_prompt=settings.system_prompt,
    )
    logger = InteractionLogger(logs_dir=tmp_path, session_id="test-session")
    agent = AgentController(settings=settings, llm_client=client, memory=memory, logger=logger)

    result = agent.run_once("   Hello from chat. \r\n")

    assert result.normalized_input == "Hello from chat."
    assert result.response_text == "Structured answer"
    assert [message.role for message in client.requests[0].messages] == ["system", "user"]
    assert [message.role for message in result.memory_snapshot] == ["user", "assistant"]

    log_path = tmp_path / "test-session.jsonl"
    assert log_path.exists()
    first_entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert first_entry["event"] == "interaction"
    assert first_entry["request"]["input"] == "Hello from chat."


def test_agent_controller_accepts_protocol_based_memory_and_log_sink(tmp_path):
    client = FakeLLMClient()
    settings = Settings(
        provider="cerebras",
        api_key="test-key",
        model="llama3.1-8b",
    )
    memory: MemoryStore = FakeMemoryStore()
    logger: InteractionLogSink = FakeLogSink(tmp_path / "protocol-log.json")

    agent = AgentController(settings=settings, llm_client=client, memory=memory, logger=logger)
    result = agent.run_once("Hello")

    assert result.response_text == "Structured answer"
    assert [message.role for message in result.memory_snapshot] == ["user", "assistant"]
    assert client.requests[0].messages[0].content == "Hello"


def test_agent_controller_declares_protocol_dependencies():
    hints = get_type_hints(AgentController.__init__)

    assert hints["memory"] is MemoryStore
    assert hints["logger"] is InteractionLogSink


def test_agent_behavior_remains_unchanged_across_provider_implementations(tmp_path):
    settings = Settings(
        provider="stub",
        model="stub-model",
        system_prompt="Be precise.",
        logs_dir=tmp_path,
        max_memory_messages=4,
    )
    primary_memory = ConversationMemory(
        max_messages=settings.max_memory_messages,
        system_prompt=settings.system_prompt,
    )
    fallback_memory = ConversationMemory(
        max_messages=settings.max_memory_messages,
        system_prompt=settings.system_prompt,
    )
    primary_agent = AgentController(
        settings=settings,
        llm_client=StubClient(model="stub-model", response_text="Structured answer"),
        memory=primary_memory,
        logger=InteractionLogger(logs_dir=tmp_path, session_id="stub-primary"),
    )
    fallback_agent = AgentController(
        settings=settings,
        llm_client=StubClient(model="stub-model", response_text="Structured answer"),
        memory=fallback_memory,
        logger=InteractionLogger(logs_dir=tmp_path, session_id="stub-secondary"),
    )

    primary_result = primary_agent.run_once("Hello")
    fallback_result = fallback_agent.run_once("Hello")

    assert primary_result.response_text == fallback_result.response_text
    assert [message.model_dump() for message in primary_result.memory_snapshot] == [
        message.model_dump() for message in fallback_result.memory_snapshot
    ]
