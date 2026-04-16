# Provider-Agnostic CLI Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a production-grade local CLI AI agent that ingests chat text, runs it through a provider-agnostic LLM layer, preserves short-term memory, and emits structured responses with safety-first controls.

**Architecture:** Use a layered Python package with strict boundaries between input adapters, LLM providers, orchestration, memory, and output adapters. Implement an OpenAI-compatible request/response schema and a single `LLMClient` protocol so Cerebras can be the first adapter without leaking provider details into the core pipeline.

**Tech Stack:** Python 3.11+, `httpx`, `pydantic`, `typer`, `pytest`

---

### Task 1: Scaffold Package And Tooling

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/local_ai_agent/__init__.py`
- Create: `src/local_ai_agent/cli.py`
- Create: `tests/test_smoke.py`

**Step 1: Write the failing test**

```python
def test_package_exposes_version():
    import local_ai_agent
    assert hasattr(local_ai_agent, "__version__")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing `__version__`

**Step 3: Write minimal implementation**

```python
__version__ = "0.1.0"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml README.md src/local_ai_agent/__init__.py src/local_ai_agent/cli.py tests/test_smoke.py
git commit -m "chore: scaffold local ai agent package"
```

### Task 2: Define OpenAI-Compatible Message Models And Config

**Files:**
- Create: `src/local_ai_agent/config.py`
- Create: `src/local_ai_agent/models.py`
- Create: `tests/test_models.py`

**Step 1: Write the failing test**

```python
from local_ai_agent.models import ChatMessage, ChatRequest


def test_chat_request_serializes_openai_style_messages():
    request = ChatRequest(
        model="llama-4",
        messages=[
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="Hello"),
        ],
    )

    payload = request.model_dump()

    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["content"] == "Hello"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL because models do not exist

**Step 3: Write minimal implementation**

```python
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/config.py src/local_ai_agent/models.py tests/test_models.py
git commit -m "feat: add chat models and config"
```

### Task 3: Define Provider Interface And Cerebras Adapter

**Files:**
- Create: `src/local_ai_agent/providers/__init__.py`
- Create: `src/local_ai_agent/providers/base.py`
- Create: `src/local_ai_agent/providers/cerebras.py`
- Create: `tests/test_provider_factory.py`

**Step 1: Write the failing test**

```python
from local_ai_agent.providers import build_provider
from local_ai_agent.config import Settings


def test_provider_factory_builds_cerebras_client():
    settings = Settings(provider="cerebras", api_key="test-key")
    client = build_provider(settings)
    assert client.provider_name == "cerebras"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_provider_factory.py -v`
Expected: FAIL because provider factory does not exist

**Step 3: Write minimal implementation**

```python
class LLMClient(Protocol):
    provider_name: str
    async def complete(self, request: ChatRequest) -> ChatResponse: ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_provider_factory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/providers tests/test_provider_factory.py
git commit -m "feat: add provider abstraction and cerebras adapter"
```

### Task 4: Implement Memory And Context Trimming

**Files:**
- Create: `src/local_ai_agent/memory.py`
- Create: `tests/test_memory.py`

**Step 1: Write the failing test**

```python
from local_ai_agent.memory import ConversationMemory


def test_memory_keeps_last_n_non_system_messages():
    memory = ConversationMemory(max_messages=4)
    for index in range(6):
        memory.add(role="user", content=f"message-{index}")

    visible = memory.recent_messages()
    assert [item.content for item in visible] == ["message-2", "message-3", "message-4", "message-5"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory.py -v`
Expected: FAIL because memory store does not exist

**Step 3: Write minimal implementation**

```python
class ConversationMemory:
    def add(self, role: str, content: str) -> None:
        ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/memory.py tests/test_memory.py
git commit -m "feat: add bounded conversation memory"
```

### Task 5: Build Deterministic Agent Pipeline

**Files:**
- Create: `src/local_ai_agent/input_adapters.py`
- Create: `src/local_ai_agent/output_adapters.py`
- Create: `src/local_ai_agent/automation.py`
- Create: `src/local_ai_agent/agent.py`
- Create: `tests/test_agent.py`

**Step 1: Write the failing test**

```python
async def test_agent_runs_input_normalize_llm_postprocess_output():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent.py -v`
Expected: FAIL because agent pipeline does not exist

**Step 3: Write minimal implementation**

```python
class AgentController:
    async def run_once(self, raw_text: str) -> AgentResult:
        ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/input_adapters.py src/local_ai_agent/output_adapters.py src/local_ai_agent/automation.py src/local_ai_agent/agent.py tests/test_agent.py
git commit -m "feat: add deterministic agent pipeline"
```

### Task 6: Add Logging, Confirmation, And CLI Commands

**Files:**
- Create: `src/local_ai_agent/logging_utils.py`
- Modify: `src/local_ai_agent/cli.py`
- Create: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
def test_cli_requires_confirmation_before_send():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL because CLI safety flow does not exist

**Step 3: Write minimal implementation**

```python
@app.command()
def reply(...):
    ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/logging_utils.py src/local_ai_agent/cli.py tests/test_cli.py
git commit -m "feat: add cli safety controls and logging"
```

### Task 7: Verify End-To-End Behavior And Document Usage

**Files:**
- Modify: `README.md`
- Test: `tests/test_cli.py`
- Test: `tests/test_agent.py`

**Step 1: Run focused test suite**

```bash
pytest tests/test_smoke.py tests/test_models.py tests/test_provider_factory.py tests/test_memory.py tests/test_agent.py tests/test_cli.py -v
```

**Step 2: Run lint/diagnostics**

Use editor diagnostics on touched files and fix any issues.

**Step 3: Document real workflow**

Add README examples for:
- stdin input
- one-shot prompt input
- confirmation-before-send
- log file location
- provider configuration

**Step 4: Re-run tests**

Run: `pytest -v`
Expected: PASS

**Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add local agent usage guide"
```
