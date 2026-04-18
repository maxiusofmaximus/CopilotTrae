# Production Readiness Hardening Implementation Plan (1-2 Days)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden the current deterministic router + terminal middleware stack so it is safe, observable, and operable in real production usage before opening the Hub module front.

**Architecture:** Keep the router deterministic and non-executing. Put production safety controls at the host boundary (`TerminalHost`) and operational controls in configuration (`Settings`) and logging sinks (JSONL). Add a minimal smoke path that exercises the real end-to-end wiring (PowerShell middleware -> `exec --json` -> interactive `exec`) without introducing Hub scope.

**Tech Stack:** Python 3.12, `pytest`, PowerShell (`pwsh`), JSONL logging, current `Settings`/runtime/router/terminal contracts

---

## Scope (Hardening Only)

In scope:

- Fail-fast configuration validation for production.
- Execution guardrails at the terminal host boundary (allowlist-based).
- Log redaction + basic log rotation/retention for JSONL files.
- Middleware safety toggles and runbook/smoke checks.

Out of scope:

- Hub module design/implementation.
- Any router behavior changes that affect determinism or introduce execution.
- UI work beyond docs/runbooks and smoke scripts.

---

## Exit Criteria (Ready For Production, Hub Can Open)

The system is "production-ready" and the Hub front can be opened only when ALL are true:

1. `pytest -q` passes on CI/local.
2. A deterministic end-to-end smoke run passes:
   - PowerShell middleware is invoked with an invalid command.
   - Middleware calls `local-ai-agent exec --json` first (machine-readable).
   - The interactive correction path runs, and a suggested command can be executed with explicit confirmation.
3. Execution guardrails are enforceable:
   - With an allowlist configured, non-allowlisted commands are blocked with a clear message.
   - The default behavior remains backward-compatible when no allowlist is configured.
4. Logs are safe and operable:
   - Secrets are redacted in interaction logs (and never written verbatim).
   - JSONL files have bounded growth (rotation/retention works).
5. A short runbook exists and matches reality:
   - How to enable/disable middleware.
   - Where logs live and how to inspect them.
   - How to reproduce common failure modes.

---

## Suggested Execution Order (Dependencies)

1. Task 1: Production config validation (foundation)
2. Task 2: Execution allowlist guardrails (safety boundary)
3. Task 3: Log redaction + rotation/retention (operability)
4. Task 4: Middleware safety toggles (operational control)
5. Task 5: Smoke script + runbook docs (operator-facing)
6. Task 6: Pilot checklist and go/no-go (final validation)

---

### Task 1: Add Production Config Validation (Fail Fast)

**Goal:** Ensure we fail fast when a production provider is selected without required secrets, and ensure critical paths are configured explicitly.

**Files:**
- Modify: `src/local_ai_agent/config.py`
- Create: `tests/test_settings_production_validation.py`

**Step 1: Write the failing tests**

Create `tests/test_settings_production_validation.py`:

```python
import pytest

from local_ai_agent.config import Settings


def test_settings_validation_allows_stub_without_api_key():
    settings = Settings(provider="stub", api_key=None)
    assert settings.provider == "stub"


def test_settings_validation_rejects_real_provider_without_api_key():
    with pytest.raises(ValueError, match="api_key"):
        Settings(provider="cerebras", api_key=None)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_settings_production_validation.py -q`
Expected: FAIL because `Settings` does not validate required secrets by provider.

**Step 3: Implement minimal validation**

In `src/local_ai_agent/config.py`:

- Add a small validation rule (Pydantic validator) such that:
  - `provider in {"stub", "failing-stub"}` can omit `api_key`.
  - all other providers require `api_key` to be present and non-empty.
- Keep behavior compatible with current defaults where `api_key` can come from env.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_settings_production_validation.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/local_ai_agent/config.py tests/test_settings_production_validation.py
git commit -m "feat: fail fast on missing production credentials"
```

---

### Task 2: Add Execution Allowlist Guardrails In `TerminalHost`

**Goal:** Enforce an optional allowlist for execution so production can restrict what may run, without changing router determinism.

**Files:**
- Modify: `src/local_ai_agent/config.py`
- Modify: `src/local_ai_agent/terminal/host.py`
- Modify: `src/local_ai_agent/cli.py`
- Test: `tests/test_terminal_host.py`

**Step 1: Write the failing tests**

In `tests/test_terminal_host.py`, add:

```python
def test_terminal_host_blocks_execution_when_allowlist_denies_command():
    # Arrange: build a host with an allowlist that does NOT include "gh"
    # RouteEnvelope must be "tool_execution" with argv ["gh", "--version"]
    # Act: handle_input("gh --version")
    # Assert: result.action == "blocked" and blocked_reason indicates allowlist denial
    ...
```

**Step 2: Run the focused test to confirm red**

Run: `pytest tests/test_terminal_host.py -q`
Expected: FAIL until allowlist is wired.

**Step 3: Implement minimal allowlist support**

Implementation requirements:

- Add an optional `exec_allowlist` to `Settings` sourced from env:
  - Env var: `LOCAL_AI_AGENT_EXEC_ALLOWLIST`
  - Format: comma-separated tool names (`"gh,git,pwsh"`)
  - Default: empty / unset means "no restriction" (backward compatible).
- In `TerminalHost`:
  - When handling `tool_execution` and executing (not dry-run), if allowlist is configured and the command's tool name is not in allowlist, return `action="blocked"` with `blocked_reason="exec_allowlist_denied"`.
  - Apply the same guard for executing the suggested command (correction execution).
- In `cli.py`:
  - Pass the allowlist into the host creation (either via `TerminalHost` ctor or by policy closure).

**Step 4: Run tests to verify green**

Run: `pytest tests/test_terminal_host.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/local_ai_agent/config.py src/local_ai_agent/terminal/host.py src/local_ai_agent/cli.py tests/test_terminal_host.py
git commit -m "feat: add optional exec allowlist guardrails"
```

---

### Task 3: Redact Secrets And Add Basic Log Rotation/Retention For JSONL

**Goal:** Prevent secrets from being written to disk and ensure JSONL logs do not grow unbounded.

**Files:**
- Modify: `src/local_ai_agent/logging_utils.py`
- Modify: `src/local_ai_agent/router/runtime_services.py`
- Modify: `src/local_ai_agent/config.py`
- Create: `src/local_ai_agent/log_safety.py`
- Create: `tests/test_log_safety.py`

**Step 1: Write failing tests for redaction**

Create `tests/test_log_safety.py`:

```python
from local_ai_agent.log_safety import redact_secrets


def test_redact_secrets_scrubs_common_keys_recursively():
    payload = {
        "api_key": "SECRET",
        "nested": {"authorization": "Bearer SECRET2"},
        "list": [{"token": "SECRET3"}],
    }
    redacted = redact_secrets(payload)
    assert redacted["api_key"] != "SECRET"
    assert "SECRET2" not in redacted["nested"]["authorization"]
    assert redacted["list"][0]["token"] != "SECRET3"
```

**Step 2: Run tests to verify red**

Run: `pytest tests/test_log_safety.py -q`
Expected: FAIL because `redact_secrets` does not exist.

**Step 3: Implement `redact_secrets`**

Create `src/local_ai_agent/log_safety.py`:

- Provide `redact_secrets(value: object) -> object` that:
  - Recursively walks dict/list structures.
  - Redacts values for keys: `api_key`, `authorization`, `token`, `access_token`, `refresh_token`, `bearer`.
  - Replaces with `"[REDACTED]"` (string).
  - Leaves non-structured types unchanged.

**Step 4: Wire redaction into log sinks**

- In `InteractionLogger.log_interaction` (`src/local_ai_agent/logging_utils.py`), redact before writing JSONL.
- In `JsonlRouterEventSink.emit` (`src/local_ai_agent/router/runtime_services.py`), redact payload before writing (defense-in-depth).

**Step 5: Add basic rotation/retention**

Add to `Settings`:

- `logs_max_bytes` (default e.g. 10_000_000)
- `logs_max_backups` (default e.g. 3)

Implement a minimal rotate-on-write strategy:

- Before appending, if `log_path` exists and size > `logs_max_bytes`:
  - Rename `log_path` -> `log_path.1`, shift existing `.1` -> `.2` ... up to `logs_max_backups`.
  - Delete the oldest beyond retention.

Apply rotation consistently to:

- interaction logs (`logs/<session>.jsonl`)
- router logs (`logs/router/<session>.jsonl`)

**Step 6: Add tests for rotation**

Extend `tests/test_log_safety.py` with a small file-based rotation test using a tiny `logs_max_bytes`.

**Step 7: Run focused tests**

Run: `pytest tests/test_log_safety.py -q`
Expected: PASS.

**Step 8: Commit**

```bash
git add src/local_ai_agent/log_safety.py src/local_ai_agent/logging_utils.py src/local_ai_agent/router/runtime_services.py src/local_ai_agent/config.py tests/test_log_safety.py
git commit -m "feat: redact secrets and rotate jsonl logs"
```

---

### Task 4: Add Middleware Operational Toggles (Kill Switch)

**Goal:** Allow safe disablement of middleware behavior without uninstalling it, and ensure failure modes are explicit.

**Files:**
- Modify: `scripts/powershell/middleware.ps1`
- Modify: `README.md`
- Test: `tests/test_powershell_middleware.py`

**Step 1: Write failing middleware toggle test**

In `tests/test_powershell_middleware.py`, add:

```python
def test_middleware_respects_disable_flag(tmp_path: Path) -> None:
    # Arrange: set env LOCAL_AI_AGENT_MIDDLEWARE_DISABLED=1
    # Provide a failing command, verify middleware does NOT call local-ai-agent at all.
    ...
```

**Step 2: Run test to verify red**

Run: `pytest tests/test_powershell_middleware.py -q`
Expected: FAIL until middleware checks the env flag.

**Step 3: Implement kill switch**

In `scripts/powershell/middleware.ps1`:

- If `LOCAL_AI_AGENT_MIDDLEWARE_DISABLED` is truthy (`1/true/yes/on`):
  - Run the command directly and exit with its `$LASTEXITCODE`.
  - Do not call `local-ai-agent` in any mode.

**Step 4: Update docs**

In `README.md`, document:

- How to disable middleware with `LOCAL_AI_AGENT_MIDDLEWARE_DISABLED`.
- Expected behavior when disabled.

**Step 5: Run focused tests**

Run: `pytest tests/test_powershell_middleware.py -q`
Expected: PASS.

**Step 6: Commit**

```bash
git add scripts/powershell/middleware.ps1 tests/test_powershell_middleware.py README.md
git commit -m "feat: add middleware kill switch for production ops"
```

---

### Task 5: Add A One-Command Smoke Script + Short Runbook

**Goal:** Give operators a single repeatable check to validate the system, and document how to run/triage it.

**Files:**
- Create: `scripts/smoke/production_readiness.ps1`
- Create: `docs/runbooks/production-readiness.md`
- Modify: `README.md`

**Step 1: Create the smoke script**

`scripts/smoke/production_readiness.ps1` should:

- Run `pytest -q` and fail if tests fail.
- Run a deterministic E2E sample with stub provider:
  - set `LOCAL_AI_AGENT_PROVIDER=stub`
  - set `LOCAL_AI_AGENT_SESSION_ID=smoke-<timestamp>`
  - set `LOCAL_AI_AGENT_LOGS_DIR` to a temp dir
  - pipe `"y"` into `middleware.ps1 github.cli --version`
- Verify that router log file is created under `$LOGS_DIR/router/<session>.jsonl`.

**Step 2: Write the runbook**

`docs/runbooks/production-readiness.md`:

- "Enable/disable middleware" section.
- "Smoke check" section (copy-paste commands).
- "Where are logs" section (interaction vs router JSONL).
- "Common failures and fixes" section:
  - provider missing API key
  - router JSON parse error
  - allowlist denies execution
  - snapshot mismatch (what it means and why it should not happen in normal middleware flow)

**Step 3: Link from README**

Add a short README link to the runbook and smoke script.

**Step 4: Commit**

```bash
git add scripts/smoke/production_readiness.ps1 docs/runbooks/production-readiness.md README.md
git commit -m "docs: add production readiness smoke script and runbook"
```

---

### Task 6: Pilot Checklist + Go/No-Go Gate

**Goal:** Validate against real usage patterns with minimal blast radius and a clear decision gate.

**Files:**
- Modify: `docs/runbooks/production-readiness.md`

**Step 1: Define a pilot run**

Add a short pilot section:

- 5-10 representative commands:
  - 2 known-good commands
  - 2 known-bad commands (typos / wrong tool name) to exercise correction flow
  - 1 command with quoting/paths (Windows edge)
  - 1 command that should be blocked by allowlist (if allowlist enabled)
- Required artifacts:
  - router JSONL file saved
  - interaction JSONL file saved

**Step 2: Go/No-Go**

Define explicit go/no-go conditions:

- Go:
  - no secrets found in JSONL logs
  - allowlist blocks correctly when enabled
  - middleware kill switch works
  - no unhandled exceptions in `pwsh` output
- No-Go:
  - any secret leakage to disk
  - unintended execution without confirmation when it should have been required
  - router/middleware breaks determinism or emits non-JSON where JSON is required (`exec --json`)

**Step 3: Commit**

```bash
git add docs/runbooks/production-readiness.md
git commit -m "docs: add pilot checklist and go/no-go gate"
```

---

## Two Execution Options

Plan saved. Two execution options:

1. **Subagent-Driven (this session)**: I use `superpowers:subagent-driven-development`, one task at a time with review checkpoints.
2. **Parallel Session (separate)**: Open a new session and run `superpowers:executing-plans` against this plan.

