# Terminal Runtime Adoption Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Connect the deterministic router to real runtime state and add a real terminal host that consumes routing decisions without giving execution authority to the router itself.

**Architecture:** Keep the router pure and snapshot-bound. Add production runtime services that build session-scoped snapshots and persist router events, then introduce a terminal host layer that consumes `RouteEnvelope` values and decides whether to execute a subprocess, print a correction, show a Hub proposal, or reject the request. The CLI will expose both the existing machine-facing `route` command and a new user-facing terminal command that uses the same routing pipeline internally.

**Tech Stack:** Python 3.12, `pytest`, `argparse`, `subprocess`, JSONL logging, existing `Settings` / runtime / router contracts

---

### Task 1: Wire Real Snapshot And Event Services Into Runtime

**Files:**
- Create: `src/local_ai_agent/router/runtime_services.py`
- Modify: `src/local_ai_agent/runtime.py`
- Modify: `src/local_ai_agent/modules/snapshot_builder.py`
- Modify: `src/local_ai_agent/config.py`
- Test: `tests/test_runtime_router_wiring.py`

**Step 1: Write the failing test**

```python
def test_build_runtime_exposes_router_runtime_with_real_snapshot_provider(tmp_path):
    settings = Settings(
        provider="stub",
        api_key="test",
        session_id="sess-1",
        logs_dir=tmp_path / "logs",
        router_tools_manifest=[],
    )

    runtime = build_runtime(settings, stdin=io.StringIO(""), stdout=io.StringIO())

    assert runtime.router_runtime is not None
    snapshot = runtime.router_runtime.snapshot_provider.get_snapshot(session_id="sess-1")
    assert snapshot.built_for_session == "sess-1"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_runtime_router_wiring.py::test_build_runtime_exposes_router_runtime_with_real_snapshot_provider -v`
Expected: FAIL because `build_runtime()` does not wire a real snapshot provider or event sink.

**Step 3: Write minimal implementation**

```python
@dataclass(slots=True)
class StaticSnapshotProvider:
    snapshot: RegistrySnapshot

    def get_snapshot(self, *, session_id: str) -> RegistrySnapshot:
        if session_id != self.snapshot.built_for_session:
            return replace(self.snapshot, built_for_session=session_id)
        return self.snapshot


@dataclass(slots=True)
class JsonlRouterEventSink:
    log_path: Path

    def emit(self, event: Any) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=True) + "\n")
```

Also:

- add `build_default_tool_registry(settings)` and `build_default_module_registry(settings)`
- change `build_registry_snapshot()` to generate a stable session-scoped snapshot version instead of the hard-coded `"generated"`
- instantiate `RouterRuntime` inside `build_runtime()`
- pass `router_runtime` into `AgentSessionRunner`

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_runtime_router_wiring.py::test_build_runtime_exposes_router_runtime_with_real_snapshot_provider -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/router/runtime_services.py src/local_ai_agent/runtime.py src/local_ai_agent/modules/snapshot_builder.py src/local_ai_agent/config.py tests/test_runtime_router_wiring.py
git commit -m "feat: wire router runtime to real snapshot services"
```

### Task 2: Add Terminal Host That Consumes Route Envelopes

**Files:**
- Create: `src/local_ai_agent/terminal_host.py`
- Create: `src/local_ai_agent/terminal_executor.py`
- Modify: `src/local_ai_agent/contracts.py`
- Test: `tests/test_terminal_host.py`

**Step 1: Write the failing test**

```python
def test_terminal_host_executes_only_tool_execution_routes():
    executor = FakeExecutor()
    output = FakeOutput()
    host = TerminalHost(executor=executor, output=output)

    result = host.handle(
        RouteEnvelope.tool_execution(
            intent="tool_execution",
            snapshot_version="snap-1",
            tool_name="gh",
            shell="powershell",
            argv=["gh", "--version"],
            confidence=1.0,
            threshold_applied=0.85,
            threshold_source="intent:tool_execution",
            resolver_path=["normalize_input"],
            evidence=["tool_name_match:gh"],
        )
    )

    assert result.exit_code == 0
    assert executor.calls == [{"argv": ["gh", "--version"], "shell": "powershell"}]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_terminal_host.py::test_terminal_host_executes_only_tool_execution_routes -v`
Expected: FAIL because no terminal host exists.

**Step 3: Write minimal implementation**

```python
class TerminalExecutor(Protocol):
    def run(self, *, argv: list[str], shell: str, cwd: str | None = None) -> int:
        ...


@dataclass(slots=True)
class TerminalHostResult:
    exit_code: int


class TerminalHost:
    def handle(self, route: RouteEnvelope, *, cwd: str | None = None) -> TerminalHostResult:
        if route.route == "tool_execution":
            exit_code = self.executor.run(
                argv=list(route.payload["argv"]),
                shell=str(route.payload["shell"]),
                cwd=cwd,
            )
            return TerminalHostResult(exit_code=exit_code)
        ...
```

Also cover:

- `command_fix` prints the suggested command and exits non-zero
- `clarification` prints options and exits non-zero
- `hub_install` prints module proposals and exits non-zero
- `policy_denied` prints the machine-readable reason and exits non-zero

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_terminal_host.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/terminal_host.py src/local_ai_agent/terminal_executor.py src/local_ai_agent/contracts.py tests/test_terminal_host.py
git commit -m "feat: add terminal host for route consumption"
```

### Task 3: Expose A User-Facing Terminal Command In CLI

**Files:**
- Modify: `src/local_ai_agent/cli.py`
- Modify: `src/local_ai_agent/runtime.py`
- Test: `tests/test_cli_terminal.py`

**Step 1: Write the failing test**

```python
def test_cli_terminal_command_routes_then_delegates_to_terminal_host():
    runtime = FakeRuntime()

    exit_code = main(
        ["terminal", "--text", "gh --version", "--shell", "powershell", "--cwd", "C:\\repo"],
        runtime=runtime,
        stdout=io.StringIO(),
    )

    assert exit_code == 0
    assert runtime.runner.route_calls
    assert runtime.terminal_host.calls
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_terminal.py::test_cli_terminal_command_routes_then_delegates_to_terminal_host -v`
Expected: FAIL because the CLI has no user-facing terminal host command.

**Step 3: Write minimal implementation**

```python
terminal = subparsers.add_parser("terminal", help="Route terminal input and apply the host decision.")
terminal.add_argument("--text", required=True)
terminal.add_argument("--shell", choices=["powershell", "bash"], required=True)
terminal.add_argument("--cwd", required=True)
```

Then:

- build a `TerminalRequest`
- call `runtime.runner.route_terminal_request(request)`
- hand the resulting envelope to `runtime.terminal_host.handle(...)`
- return the host exit code

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_terminal.py::test_cli_terminal_command_routes_then_delegates_to_terminal_host -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/cli.py src/local_ai_agent/runtime.py tests/test_cli_terminal.py
git commit -m "feat: add terminal host cli command"
```

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

Run: `pytest tests/test_runtime_router_wiring.py tests/test_terminal_host.py tests/test_cli_terminal.py tests/test_terminal_runtime_e2e.py tests/test_cli.py tests/test_router_contracts.py tests/test_router_policies.py tests/test_tool_registry.py tests/test_module_registry.py tests/test_router_pipeline.py tests/test_command_fix.py tests/test_router_integration.py tests/test_router_events.py tests/test_router_escalation.py tests/test_router_contract_invariants.py -v`
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

## Suggested Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
