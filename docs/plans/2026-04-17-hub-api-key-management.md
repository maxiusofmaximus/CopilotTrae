# Hub API Key Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a minimal Hub-side credential service that manages provider API keys safely, starts with an env-var backend, and prepares launch environments without changing router or runtime behavior.

**Architecture:** Keep all credential logic above `Settings.from_env()`. Introduce a small `hub` package with explicit credential contracts, an env-backed backend, and a Hub-facing service that validates provider setup from backend status plus provider descriptors. The backend reports source and presence only; provider-level structural validation stays in the service so backend implementations remain generic and interchangeable.

**Tech Stack:** Python 3.12, `pytest`, stdlib `os`/`typing`, existing `Settings` env contract, existing secret redaction policy in `src/local_ai_agent/log_safety.py`

---

### Task 1: Add Credential Contracts And Secret Type

**Files:**
- Create: `src/local_ai_agent/hub/__init__.py`
- Create: `src/local_ai_agent/hub/credentials_contracts.py`
- Create: `tests/test_hub_credentials_contracts.py`

**Step 1: Write the failing tests**

Add contract tests for:

- `SecretValue` redacts itself in `str()` and `repr()`
- `SecretValue` rejects empty input
- `SecretValue` can only hand its raw value to a `SecretSink`
- `CredentialDescriptor`, `CredentialStatus`, and `CredentialWriteResult` carry only safe metadata

```python
import pytest

from local_ai_agent.hub.credentials_contracts import SecretSink, SecretValue


class SpySink:
    def __init__(self) -> None:
        self.accepted: list[str] = []

    def accept_secret(self, secret: str) -> None:
        self.accepted.append(secret)


def test_secret_value_redacts_string_representations() -> None:
    secret = SecretValue("abc-123")

    assert str(secret) == "[REDACTED]"
    assert repr(secret) == "[REDACTED]"


def test_secret_value_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        SecretValue("   ")


def test_secret_value_only_writes_through_sink() -> None:
    secret = SecretValue("abc-123")
    sink = SpySink()

    secret.write_into(sink)

    assert sink.accepted == ["abc-123"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_hub_credentials_contracts.py -v`
Expected: FAIL because the `hub` credential contracts do not exist yet.

**Step 3: Write minimal implementation**

Create `src/local_ai_agent/hub/credentials_contracts.py` with:

- `CredentialState`
- `CredentialSourceKind`
- `CredentialScope`
- `CredentialDescriptor`
- `CredentialStatus`
- `CredentialWriteResult`
- `SecretSink` protocol
- `SecretValue`
- `CredentialBackend` protocol

Important design rule:

- `CredentialBackend` does **not** expose `validate_provider_setup()`
- backend responsibility is source-specific read/write/status/build-env
- service responsibility is provider-specific validation derived from descriptors plus `get_status()`

Minimal implementation sketch:

```python
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol, Sequence


class CredentialState(str, Enum):
    CONFIGURED = "configured"
    MISSING = "missing"
    PARTIAL = "partial"
    INVALID = "invalid"


class SecretSink(Protocol):
    def accept_secret(self, secret: str) -> None: ...


class SecretValue:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not value or not value.strip():
            raise ValueError("SecretValue cannot be empty.")
        self._value = value

    def __repr__(self) -> str:
        return "[REDACTED]"

    def __str__(self) -> str:
        return "[REDACTED]"

    def write_into(self, sink: SecretSink) -> None:
        sink.accept_secret(self._value)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_hub_credentials_contracts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/hub/__init__.py src/local_ai_agent/hub/credentials_contracts.py tests/test_hub_credentials_contracts.py
git commit -m "feat: add hub credential contracts"
```

### Task 2: Add Env Credential Backend

**Files:**
- Create: `src/local_ai_agent/hub/env_credentials.py`
- Create: `tests/test_hub_env_credentials.py`

**Step 1: Write the failing tests**

Add backend tests for:

- known provider descriptors are exposed for `cerebras`, `openai_compatible`, and `fallback`
- `get_status("cerebras")` reports `configured` when either `LOCAL_AI_AGENT_API_KEY` or `CEREBRAS_API_KEY` exists
- `set_secret()` writes the correct env var for the provider and scope
- `clear_secret()` removes only provider-owned env vars
- `build_launch_env()` returns a merged env dict without mutating the input mapping

```python
def test_env_backend_reports_cerebras_configured_when_local_api_key_present(monkeypatch):
    monkeypatch.setenv("LOCAL_AI_AGENT_API_KEY", "test-key")
    backend = EnvCredentialBackend()

    status = backend.get_status("cerebras")

    assert status.state is CredentialState.CONFIGURED
    assert status.has_secret is True
    assert status.source_kind is CredentialSourceKind.ENV


def test_env_backend_build_launch_env_returns_copy(monkeypatch):
    backend = EnvCredentialBackend()
    base_env = {"LOCAL_AI_AGENT_PROVIDER": "cerebras"}

    launch_env = backend.build_launch_env(base_env, "cerebras")

    assert launch_env is not base_env
    assert launch_env["LOCAL_AI_AGENT_PROVIDER"] == "cerebras"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_hub_env_credentials.py -v`
Expected: FAIL because the env backend does not exist yet.

**Step 3: Write minimal implementation**

Create `src/local_ai_agent/hub/env_credentials.py` with:

- provider descriptor registry
- a small env writer abstraction for `PROCESS` scope first
- `EnvCredentialBackend` implementing `CredentialBackend`
- source-safe `get_status()` returning metadata only
- `set_secret()` using `SecretValue.write_into(...)`
- `clear_secret()` removing only mapped keys
- `build_launch_env()` composing a new dict compatible with `Settings.from_env()`

Keep scope intentionally minimal:

- support `CredentialScope.PROCESS` in implementation
- if `USER` scope is requested, raise a typed backend error for now instead of inventing persistence behavior
- do not edit `.env` in this first cut

Minimal implementation sketch:

```python
class _EnvSecretSink:
    def __init__(self, env: dict[str, str], key: str) -> None:
        self._env = env
        self._key = key

    def accept_secret(self, secret: str) -> None:
        self._env[self._key] = secret


class EnvCredentialBackend:
    def set_secret(self, provider_id: str, secret: SecretValue, scope: CredentialScope) -> CredentialWriteResult:
        if scope is not CredentialScope.PROCESS:
            raise CredentialWriteError("Only process scope is supported by EnvCredentialBackend.")
        sink = _EnvSecretSink(self._process_env, "LOCAL_AI_AGENT_API_KEY")
        secret.write_into(sink)
        return CredentialWriteResult(...)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_hub_env_credentials.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/hub/env_credentials.py tests/test_hub_env_credentials.py
git commit -m "feat: add env credential backend"
```

### Task 3: Add Hub Credential Service Adapter

**Files:**
- Create: `src/local_ai_agent/hub/credential_service.py`
- Create: `tests/test_hub_credential_service.py`

**Step 1: Write the failing tests**

Add service tests for:

- `list_credentials()` returns descriptors from the backend
- `validate_provider_setup()` derives validation from `get_status()` plus descriptor rules
- `validate_provider_setup("cerebras")` treats either `LOCAL_AI_AGENT_API_KEY` or `CEREBRAS_API_KEY` as sufficient
- `validate_provider_setup("fallback")` requires `LOCAL_AI_AGENT_FALLBACK_API_KEY`
- `build_launch_env()` delegates to backend and preserves compatibility with `Settings.from_env()`

```python
def test_service_validate_provider_setup_derives_from_backend_status():
    backend = FakeBackend(
        statuses={
            "cerebras": CredentialStatus(
                provider_id="cerebras",
                state=CredentialState.CONFIGURED,
                source_kind=CredentialSourceKind.ENV,
                has_secret=True,
                missing_fields=(),
                safe_summary="configured from env",
            )
        }
    )
    service = HubCredentialService(backend)

    status = service.validate_provider_setup("cerebras")

    assert status.state is CredentialState.CONFIGURED


def test_service_build_launch_env_returns_settings_compatible_env(monkeypatch):
    backend = FakeBackend(...)
    service = HubCredentialService(backend)

    launch_env = service.build_launch_env({"LOCAL_AI_AGENT_PROVIDER": "cerebras"}, "cerebras")

    assert launch_env["LOCAL_AI_AGENT_PROVIDER"] == "cerebras"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_hub_credential_service.py -v`
Expected: FAIL because the Hub-facing service adapter does not exist yet.

**Step 3: Write minimal implementation**

Create `src/local_ai_agent/hub/credential_service.py` with:

- `HubCredentialService`
- typed service errors such as `UnknownProviderError`, `SecretValidationError`, `CredentialBackendError`, `CredentialWriteError`, `CredentialDeleteError`, and `LaunchEnvBuildError`
- `validate_provider_setup()` implemented in the service, not in the backend
- `validate_provider_setup()` derived from:
  - provider descriptor
  - backend `get_status()`
  - provider-specific required env var rules

Do not add:

- provider HTTP connectivity checks
- `.env` editing
- router/runtime hooks
- any logging of secret-bearing objects

Minimal implementation sketch:

```python
class HubCredentialService:
    def __init__(self, backend: CredentialBackend) -> None:
        self._backend = backend
        self._descriptors = {item.provider_id: item for item in backend.list_descriptors()}

    def validate_provider_setup(self, provider_id: str) -> CredentialStatus:
        descriptor = self._descriptors.get(provider_id)
        if descriptor is None:
            raise UnknownProviderError(provider_id)
        status = self._backend.get_status(provider_id)
        return status
```

Then tighten validation minimally:

- if provider is known and `missing_fields` is empty with `has_secret=True`, return `CONFIGURED`
- if required key set is incomplete, return `MISSING` or `PARTIAL`
- never expose secret material in returned status

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_hub_credential_service.py -v`
Expected: PASS

**Step 5: Run focused suite**

Run: `pytest tests/test_hub_credentials_contracts.py tests/test_hub_env_credentials.py tests/test_hub_credential_service.py tests/test_log_safety.py tests/test_settings_production_validation.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/local_ai_agent/hub/credential_service.py tests/test_hub_credential_service.py
git commit -m "feat: add hub credential service adapter"
```
