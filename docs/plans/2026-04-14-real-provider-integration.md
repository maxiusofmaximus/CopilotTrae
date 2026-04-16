# Real Provider Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a real generic `openai_compatible` `LLMClient` and wire it through the existing provider factory and fallback composition seams without changing `AgentController`, `AgentSessionRunner`, or the CLI.

**Architecture:** Introduce a single `GenericOpenAICompatibleClient` that handles only HTTP transport, auth, retries, and payload/response mapping for OpenAI-style `/chat/completions` APIs. Keep all endpoint selection in settings and provider factory code, including separate primary and fallback endpoint credentials so different compatible providers can be composed without new core logic.

**Tech Stack:** Python 3.12, `httpx`, `pydantic`, `pytest`, existing provider protocol and fallback wrapper

---

### Task 1: Add Red Tests For The Generic Provider Adapter

**Files:**
- Create: `tests/test_openai_compatible_client.py`

**Step 1: Write the failing test**

```python
def test_openai_compatible_client_posts_openai_style_payload():
    client = GenericOpenAICompatibleClient(
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        timeout_seconds=5,
        max_retries=1,
        provider_name="openai_compatible",
        http_client=http_client,
    )
    response = client.complete(ChatRequest(...))
    assert response.content == "Ready."
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_openai_compatible_client.py -v`
Expected: FAIL because the client does not exist.

**Step 3: Write minimal implementation**

```python
class GenericOpenAICompatibleClient:
    provider_name = "openai_compatible"
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_openai_compatible_client.py -v`
Expected: PASS

### Task 2: Add Red Tests For Config-Driven Factory Selection

**Files:**
- Modify: `tests/test_provider_factory.py`

**Step 1: Write the failing tests**

```python
def test_provider_factory_builds_openai_compatible_client():
    settings = Settings(
        provider="openai_compatible",
        api_key="test-key",
        base_url="https://openrouter.ai/api/v1",
        model="openai/gpt-4o-mini",
    )
    client = build_provider(settings)
    assert isinstance(client, GenericOpenAICompatibleClient)


def test_provider_factory_can_fallback_to_openai_compatible_client():
    settings = Settings(
        provider="failing-stub",
        fallback_provider="openai_compatible",
        fallback_api_key="fallback-key",
        fallback_base_url="https://openrouter.ai/api/v1",
        fallback_model="openai/gpt-4o-mini",
    )
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_provider_factory.py -v`
Expected: FAIL because the factory does not know about the generic provider or fallback-specific settings.

**Step 3: Write minimal implementation**

```python
if provider_name == "openai_compatible":
    return GenericOpenAICompatibleClient(...)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_provider_factory.py -v`
Expected: PASS

### Task 3: Add Red Tests For Fallback Across Real And Stub Providers

**Files:**
- Modify: `tests/test_provider_factory.py`

**Step 1: Write the failing test**

```python
def test_openai_compatible_fallback_handles_primary_provider_failure():
    client = build_provider(settings)
    response = client.complete(ChatRequest(...))
    assert response.provider == "openai_compatible"
```

**Step 2: Run the targeted test to verify it fails**

Run: `python -m pytest tests/test_provider_factory.py::test_openai_compatible_fallback_handles_primary_provider_failure -v`
Expected: FAIL because fallback-specific endpoint configuration or client injection is missing.

**Step 3: Write minimal implementation**

```python
fallback_settings = ProviderEndpointSettings(...)
fallback = _build_single_provider(settings.fallback_provider, fallback_settings)
```

**Step 4: Run the targeted test to verify it passes**

Run: `python -m pytest tests/test_provider_factory.py::test_openai_compatible_fallback_handles_primary_provider_failure -v`
Expected: PASS

### Task 4: Implement The Generic OpenAI-Compatible Provider

**Files:**
- Modify: `src/local_ai_agent/config.py`
- Create: `src/local_ai_agent/providers/openai_compatible.py`
- Modify: `src/local_ai_agent/providers/__init__.py`

**Step 1:** Add fallback endpoint settings so the fallback provider can use a different `base_url`, `api_key`, and `model` from the primary provider.
**Step 2:** Implement `GenericOpenAICompatibleClient` with OpenAI-style transport, retry handling, and response parsing.
**Step 3:** Register `openai_compatible` in the provider factory using primary or fallback endpoint settings depending on which leg is being built.
**Step 4:** Re-run focused tests until green.

### Task 5: Verify Boundaries

**Files:**
- Test: `tests/`
- Diagnostics: touched source and test files

**Step 1:** Run `python -m pytest -v`.
**Step 2:** Run diagnostics on touched files and fix issues.
**Step 3:** Confirm no changes were required in `agent.py`, `session_runner.py`, or `cli.py`.
