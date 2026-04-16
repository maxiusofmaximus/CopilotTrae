# Boundary-Tightening Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the local AI agent so the core depends only on protocols, orchestration moves into an application-layer session runner, and the CLI becomes a thin shell with zero business logic.

**Architecture:** Introduce explicit contracts for memory, logging, input, and output so the core agent can remain deterministic and fully isolated from transport and interface concerns. Move multi-turn flow, input selection, side-effect confirmation, and output routing into a new `AgentSessionRunner`, leaving `cli.py` responsible only for argument parsing, dependency construction, and exit-code handling.

**Tech Stack:** Python 3.11+, `httpx`, `pydantic`, `argparse`, `pytest`

---

### Task 1: Introduce Runtime Contracts

**Files:**
- Create: `src/local_ai_agent/contracts.py`
- Modify: `src/local_ai_agent/memory.py`
- Modify: `src/local_ai_agent/logging_utils.py`
- Modify: `tests/test_memory.py`
- Create: `tests/test_contracts.py`

**Step 1: Write the failing test**

```python
from local_ai_agent.contracts import MemoryStore, InteractionLogSink
from local_ai_agent.logging_utils import InteractionLogger
from local_ai_agent.memory import ConversationMemory


def test_memory_and_logger_satisfy_runtime_contracts(tmp_path):
    memory = ConversationMemory(max_messages=2, system_prompt="System prompt")
    logger = InteractionLogger(logs_dir=tmp_path, session_id="session")

    assert isinstance(memory, MemoryStore)
    assert isinstance(logger, InteractionLogSink)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_contracts.py -v`
Expected: FAIL because the runtime contracts do not exist

**Step 3: Write minimal implementation**

```python
@runtime_checkable
class MemoryStore(Protocol):
    def build_request_messages(self, user_input: str) -> list[ChatMessage]: ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_contracts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/contracts.py src/local_ai_agent/memory.py src/local_ai_agent/logging_utils.py tests/test_contracts.py tests/test_memory.py
git commit -m "refactor: add runtime contracts for memory and logging"
```

### Task 2: Refactor Core Agent To Depend Only On Protocols

**Files:**
- Modify: `src/local_ai_agent/agent.py`
- Modify: `tests/test_agent.py`

**Step 1: Write the failing test**

```python
def test_agent_controller_accepts_protocol_based_memory_and_log_sink():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent.py -v`
Expected: FAIL because the controller still requires concrete classes

**Step 3: Write minimal implementation**

```python
class AgentController:
    def __init__(self, settings: Settings, llm_client: LLMClient, memory: MemoryStore, logger: InteractionLogSink) -> None:
        ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/agent.py tests/test_agent.py
git commit -m "refactor: decouple core agent from concrete collaborators"
```

### Task 3: Extract AgentSessionRunner

**Files:**
- Create: `src/local_ai_agent/session_runner.py`
- Modify: `src/local_ai_agent/input_adapters.py`
- Modify: `src/local_ai_agent/output_adapters.py`
- Create: `tests/test_session_runner.py`

**Step 1: Write the failing test**

```python
def test_session_runner_resolves_text_runs_agent_and_routes_outputs():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_session_runner.py -v`
Expected: FAIL because the session runner does not exist

**Step 3: Write minimal implementation**

```python
class AgentSessionRunner:
    def run_reply(self, request: ReplyRequest) -> SessionResult:
        ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_session_runner.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/session_runner.py src/local_ai_agent/input_adapters.py src/local_ai_agent/output_adapters.py tests/test_session_runner.py
git commit -m "refactor: move orchestration into session runner"
```

### Task 4: Move Chat Loop And Side-Effect Policy Out Of CLI

**Files:**
- Modify: `src/local_ai_agent/session_runner.py`
- Modify: `tests/test_session_runner.py`
- Modify: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
def test_chat_mode_loop_and_copy_confirmation_live_in_session_runner():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_session_runner.py tests/test_cli.py -v`
Expected: FAIL because orchestration still lives in the CLI

**Step 3: Write minimal implementation**

```python
def run_chat(self, request: ChatSessionRequest) -> int:
    ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_session_runner.py tests/test_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/session_runner.py tests/test_session_runner.py tests/test_cli.py
git commit -m "refactor: relocate chat flow and side-effect policy"
```

### Task 5: Reduce CLI To Thin Shell

**Files:**
- Modify: `src/local_ai_agent/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
def test_cli_parses_arguments_builds_runtime_and_delegates_to_runner():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL because the CLI still contains orchestration logic

**Step 3: Write minimal implementation**

```python
def main(...):
    args = parser.parse_args(...)
    runtime = runtime or build_runtime(settings)
    return runtime.runner.run_command(args)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/cli.py tests/test_cli.py
git commit -m "refactor: thin cli to parsing and delegation"
```

### Task 6: Verify Boundary Enforcement

**Files:**
- Modify: `README.md`
- Test: `tests/test_contracts.py`
- Test: `tests/test_agent.py`
- Test: `tests/test_session_runner.py`
- Test: `tests/test_cli.py`

**Step 1: Run focused boundary suite**

```bash
pytest tests/test_contracts.py tests/test_agent.py tests/test_session_runner.py tests/test_cli.py -v
```

**Step 2: Run full suite**

```bash
pytest -v
```

**Step 3: Run diagnostics**

Use editor diagnostics on all touched files and fix any issues.

**Step 4: Update documentation**

Document the three-layer architecture and the protocol boundaries in `README.md`.

**Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document core app and interface boundaries"
```
