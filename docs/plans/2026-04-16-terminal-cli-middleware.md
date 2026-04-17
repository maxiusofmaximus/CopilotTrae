# Terminal CLI Middleware Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add usable terminal middleware commands that route real shell input through the deterministic router and execute only through `CommandExecutor`.

**Architecture:** Keep the router JSON-only and add a thin CLI middleware around `TerminalHost`. Use a lightweight router bootstrap in `runtime.py` so `route`, `exec`, and `terminal` work without building the full chat runtime or requiring model configuration.

**Tech Stack:** Python 3.11+, stdlib `argparse`/`shutil`/`pathlib`, existing router runtime, `pytest`

---

### Task 1: Add CLI integration tests

**Files:**
- Create: `tests/test_terminal_integration.py`
- Modify: `src/local_ai_agent/cli.py`

**Step 1: Write the failing test**

```python
def test_cli_exec_prompts_before_running_command_fix():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_terminal_integration.py -q`
Expected: FAIL because `exec` and `terminal` commands do not exist yet.

### Task 2: Add lightweight terminal runtime bootstrap

**Files:**
- Modify: `src/local_ai_agent/runtime.py`

**Step 1: Write the minimal implementation**

```python
def build_router_runtime(settings: Settings) -> RouterRuntime:
    ...
```

**Step 2: Verify route/exec can resolve commands without chat runtime**

Run: `pytest tests/test_terminal_integration.py -q`
Expected: still FAIL until CLI calls the bootstrap.

### Task 3: Wire `exec` and `terminal`

**Files:**
- Modify: `src/local_ai_agent/cli.py`
- Modify: `src/local_ai_agent/terminal/host.py`

**Step 1: Add parser entries and interactive prompt handling**

```python
exec_parser = subparsers.add_parser("exec", ...)
terminal_parser = subparsers.add_parser("terminal", ...)
```

**Step 2: Keep command execution inside `TerminalHost`**

```python
def execute_suggested_command(self, result: TerminalHostResult) -> TerminalHostResult:
    ...
```

### Task 4: Add PowerShell wrapper

**Files:**
- Create: `scripts/powershell/middleware.ps1`

**Step 1: Add a simple wrapper**

```powershell
local-ai-agent exec "<command>"
```

**Step 2: Add route fallback shape for future interception**

Use `local-ai-agent route` to inspect the JSON route before delegating to `exec`.

### Task 5: Verify and harden

**Files:**
- Test: `tests/test_terminal_integration.py`
- Test: existing full suite

**Step 1: Run focused tests**

Run: `pytest tests/test_terminal_integration.py tests/test_terminal_host.py tests/test_cli.py -q`
Expected: PASS

**Step 2: Run full suite**

Run: `pytest`
Expected: PASS
