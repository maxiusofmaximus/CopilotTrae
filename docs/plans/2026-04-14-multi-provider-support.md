# Multi-Provider Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add settings-driven provider selection and optional provider fallback through the existing `LLMClient` abstraction without changing `AgentController` or CLI behavior.

**Architecture:** Keep provider-specific logic inside the provider package and runtime composition root. Extend the provider factory to build either a concrete provider or a composite fallback wrapper, and validate the abstraction with deterministic stub providers plus agent-level invariance tests.

**Tech Stack:** Python 3.12, `pydantic`, `pytest`, existing provider protocol and runtime composition layer

---

### Task 1: Add Red Tests For Provider Selection

**Files:**
- Modify: `tests/test_provider_factory.py`
- Test: `tests/test_runtime.py`

**Step 1: Write the failing test**

```python
def test_provider_factory_builds_stub_client():
    settings = Settings(provider="stub", model="stub-model")
    client = build_provider(settings)
    assert client.provider_name == "stub"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_provider_factory.py::test_provider_factory_builds_stub_client -v`
Expected: FAIL because the stub provider is unsupported.

**Step 3: Write minimal implementation**

```python
if provider_name == "stub":
    return StubClient(model=settings.model)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_provider_factory.py::test_provider_factory_builds_stub_client -v`
Expected: PASS

### Task 2: Add Red Tests For Fallback Composition

**Files:**
- Modify: `tests/test_provider_factory.py`

**Step 1: Write the failing tests**

```python
def test_provider_factory_wraps_primary_with_fallback():
    settings = Settings(provider="failing-stub", fallback_provider="stub")
    client = build_provider(settings)
    response = client.complete(ChatRequest(model="stub", messages=[ChatMessage(role="user", content="hi")]))
    assert response.provider == "stub"


def test_fallback_does_not_handle_business_logic_errors():
    client = FallbackLLMClient(primary=ValueErrorClient(), fallback=StubClient(model="stub"))
    with pytest.raises(ValueError):
        client.complete(ChatRequest(model="stub", messages=[ChatMessage(role="user", content="hi")]))
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_provider_factory.py -v`
Expected: FAIL because the fallback wrapper and failing stub do not exist.

**Step 3: Write minimal implementation**

```python
class FallbackLLMClient:
    def complete(self, request: ChatRequest) -> ChatResponse:
        try:
            return self.primary.complete(request)
        except ProviderError:
            return self.fallback.complete(request)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_provider_factory.py -v`
Expected: PASS

### Task 3: Add Red Tests For Agent Invariance

**Files:**
- Modify: `tests/test_agent.py`

**Step 1: Write the failing test**

```python
def test_agent_behavior_is_provider_agnostic():
    first_result = first_agent.run_once("Hello")
    second_result = second_agent.run_once("Hello")
    assert first_result.response_text == second_result.response_text
    assert [m.content for m in first_result.memory_snapshot] == [m.content for m in second_result.memory_snapshot]
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agent.py::test_agent_behavior_is_provider_agnostic -v`
Expected: FAIL because the second concrete provider path is not wired yet.

**Step 3: Write minimal implementation**

```python
stub_provider = StubClient(model=settings.model, response_text="stub-response")
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agent.py::test_agent_behavior_is_provider_agnostic -v`
Expected: PASS

### Task 4: Implement Provider Selection And Fallback

**Files:**
- Modify: `src/local_ai_agent/config.py`
- Modify: `src/local_ai_agent/providers/__init__.py`
- Create: `src/local_ai_agent/providers/stub.py`
- Create: `src/local_ai_agent/providers/fallback.py`

**Step 1:** Add settings for `fallback_provider` and any minimal stub configuration needed for deterministic tests.
**Step 2:** Implement `StubClient` and `FailingStubClient` as concrete `LLMClient` adapters.
**Step 3:** Implement `FallbackLLMClient` that catches only provider transport/response failures and delegates to the fallback.
**Step 4:** Update the provider factory to assemble primary and optional fallback clients from settings.
**Step 5:** Run focused tests until green.

### Task 5: Verify Boundaries

**Files:**
- Test: `tests/`
- Diagnostics: touched source and test files

**Step 1:** Run `python -m pytest -v`.
**Step 2:** Run diagnostics on touched files and fix issues.
**Step 3:** Confirm no provider-specific branching was added to `AgentController`, `session_runner.py`, or `cli.py`.
