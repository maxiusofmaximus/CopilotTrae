# Terminal Runtime Adoption Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Connect the deterministic router to real runtime state and complete the runtime adoption path without redoing the router, terminal host, or CLI surfaces that already exist.

**Architecture:** Keep the router pure and snapshot-bound. Reuse the existing `RouterRuntime`, `TerminalHost`, `CommandExecutor`, `route`, `exec`, and `terminal` surfaces. Fill only the remaining gaps: inject `router_runtime` from `build_runtime()`, make `snapshot_version` stable per session, persist router events to JSONL, and introduce a swappable `snapshot_provider` abstraction.

**Tech Stack:** Python 3.12, `pytest`, `argparse`, `subprocess`, JSONL logging, existing `Settings` / runtime / router / terminal contracts

---

## Current Repo Reality

The repo already has the following pieces implemented:

- `src/local_ai_agent/terminal/host.py`
- `src/local_ai_agent/terminal/executor.py`
- CLI commands: `route`, `exec`, and `terminal`
- `RouterRuntime` in `src/local_ai_agent/runtime.py` with typed event emission
- terminal coverage in `tests/test_terminal_integration.py`, `tests/test_terminal_host.py`, and `tests/test_terminal_ux.py`

This plan intentionally avoids rebuilding any of that.

---

### Task 1: Wire Missing Runtime Services Into `build_runtime()`

**Files:**
- Create: `src/local_ai_agent/router/runtime_services.py`
- Modify: `src/local_ai_agent/runtime.py`
- Modify: `src/local_ai_agent/modules/snapshot_builder.py`
- Modify: `src/local_ai_agent/config.py`
- Create: `tests/test_runtime_router_wiring.py`

**Step 1: Write the failing test**

```python
def test_build_runtime_injects_router_runtime_and_persists_events(tmp_path):
    settings = Settings(
        provider="stub",
        api_key="test",
        session_id="sess-1",
        logs_dir=tmp_path / "logs",
    )

    runtime = build_runtime(settings, stdin=io.StringIO(""), stdout=io.StringIO())

    assert runtime.router_runtime is not None

    request = TerminalRequest(
        request_id="req-1",
        session_id="sess-1",
        shell="powershell",
        raw_input="gh --version",
        cwd="C:\\repo",
        snapshot_version=runtime.router_runtime.snapshot.snapshot_version,
        requested_mode="json",
    )

    _ = runtime.router_runtime.resolve(request)

    assert (settings.logs_dir / "router" / "sess-1.jsonl").exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_runtime_router_wiring.py::test_build_runtime_injects_router_runtime_and_persists_events -v`
Expected: FAIL because `build_runtime()` does not yet inject a real `router_runtime` and router events are not persisted.

**Step 3: Write minimal implementation**

Implementation requirements:

- Add `snapshot_provider` abstraction (interchangeable)
  - Protocol surface: `get_snapshot(session_id: str) -> RegistrySnapshot`
  - Default implementation may be static-per-session, but must remain swappable
- Add `JsonlRouterEventSink`
  - writes JSONL with `ensure_ascii=True`
  - stores logs under `${logs_dir}/router/${session_id}.jsonl`
- Update `build_runtime()` to populate `AppRuntime.router_runtime`
- Keep the existing `RouterRuntime` and `TerminalHost` behavior intact

Also:

- Change `build_registry_snapshot()` so `snapshot_version` is stable per session instead of hard-coded `"generated"`
- Only extend `config.py` if a real configuration gap appears while implementing the above

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_runtime_router_wiring.py::test_build_runtime_injects_router_runtime_and_persists_events -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/router/runtime_services.py src/local_ai_agent/runtime.py src/local_ai_agent/modules/snapshot_builder.py src/local_ai_agent/config.py tests/test_runtime_router_wiring.py
git commit -m "feat: inject router runtime into build_runtime"
```

---

### Task 2: Keep Existing Terminal Host Paths And Coverage

**Files:**
- Use existing: `src/local_ai_agent/terminal/host.py`
- Use existing: `src/local_ai_agent/terminal/executor.py`
- Reuse existing tests: `tests/test_terminal_integration.py`, `tests/test_terminal_host.py`, `tests/test_terminal_ux.py`
- Add only the missing runtime wiring coverage from Task 1: `tests/test_runtime_router_wiring.py`

**Step 1: Validate existing coverage**

Run: `pytest tests/test_terminal_host.py tests/test_terminal_integration.py tests/test_terminal_ux.py -v`
Expected: PASS

**Step 2: Do not duplicate host tests**

This task is an alignment constraint, not a rebuild task:

- do not introduce `src/local_ai_agent/terminal_host.py`
- do not introduce `src/local_ai_agent/terminal_executor.py`
- do not create a parallel test suite for behaviors that are already covered

**Step 3: No code changes unless Task 1 exposes a real gap**

If Task 1 wiring reveals a missing host/runtime seam, patch it minimally in the existing files and reuse the current test modules.

No commit is needed for this task if it remains plan-only.

---

### Task 3: Reduce CLI Scope To Wiring Cleanup Only

**Files:**
- Modify only if needed: `src/local_ai_agent/cli.py`
- Modify only if needed: `src/local_ai_agent/runtime.py`
- Reuse existing terminal coverage unless behavior changes

The user-facing command surface already exists. The remaining decision is whether `exec` and `terminal` need consolidation.

Recommended default:

- keep `exec` as the one-shot middleware-facing surface
- keep `terminal` as the interactive loop surface
- let Task 1 wiring make both cleaner automatically by sourcing `router_runtime` from `build_runtime()`

Only make code changes here if Task 1 reveals duplicated wiring worth consolidating internally.

If an internal cleanup is needed:

- share router-runtime acquisition
- share terminal-host construction
- avoid any CLI surface change
- avoid new tests unless behavior changes

Commit only if `cli.py` or `runtime.py` actually changes in this task.

---

### Task 4: Verify End-To-End Wiring And Document Operational Flow

**Files:**
- Create: `tests/test_terminal_runtime_e2e.py`
- Modify: `README.md`
- Modify: `docs/plans/2026-04-16-terminal-runtime-adoption-implementation.md`

**Step 1: Write the failing test**

```python
def test_terminal_command_uses_real_runtime_and_persists_router_events(tmp_path):
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_terminal_runtime_e2e.py -v`
Expected: FAIL because the full host/runtime path is not verified yet.

**Step 3: Write minimal implementation**

Add:

- README section for `terminal` vs `route`
- operational note that router remains non-executing while the host is the only layer allowed to execute
- event log location and shape

If needed, add a tiny helper in runtime to expose the router event log path for assertions.

**Step 4: Run focused suite and verify it passes**

Run: `pytest tests/test_runtime_router_wiring.py tests/test_terminal_host.py tests/test_terminal_integration.py tests/test_terminal_ux.py tests/test_terminal_runtime_e2e.py tests/test_cli.py tests/test_router_contracts.py tests/test_router_policies.py tests/test_tool_registry.py tests/test_module_registry.py tests/test_router_pipeline.py tests/test_command_fix.py tests/test_router_integration.py tests/test_router_events.py tests/test_router_contract_invariants.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_terminal_runtime_e2e.py README.md docs/plans/2026-04-16-terminal-runtime-adoption-implementation.md
git commit -m "docs: record terminal runtime adoption flow"
```

## Constraints To Preserve

- The router never executes subprocesses.
- `route` remains JSON-only for machine consumers.
- The terminal host is the only layer allowed to execute a routed command.
- Hub proposals remain advisory.
- External assistance stays policy-gated and non-autonomous.
- This phase does not rebuild the host or CLI surfaces already validated in hardening.

## Suggested Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
