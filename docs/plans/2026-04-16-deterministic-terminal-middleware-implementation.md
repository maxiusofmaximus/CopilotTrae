# Deterministic Terminal Middleware Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python middleware layer that routes terminal input deterministically via JSON contracts to local tools, correction logic, Hub proposals, and optional external assistance without turning the system into an autonomous agent.

**Architecture:** Keep `src/local_ai_agent/agent.py` unchanged as the existing deterministic core and add a parallel router stack around it. Materialize `TerminalRequest`, `RegistrySnapshot`, policies, and route envelopes in Python first, then wire runtime and CLI boundaries to consume those contracts without granting the router any direct mutation or execution authority.

**Tech Stack:** Python 3.11+, stdlib `dataclasses`/`enum`/`pathlib`, `pydantic`, `pytest`

---

## Implementation Rules

- Do not modify `src/local_ai_agent/agent.py`.
- Keep the router pure: no subprocess execution, no filesystem probing during request resolution, no direct Hub mutation.
- Treat `tmp/architecture_compare/*` and `Claudia/` as reference-only repositories; do not import runtime code from them.
- Prefer additive changes in new packages: `router/`, `tools/`, `modules/`, `hub/`.
- Keep JSON contracts machine-readable and stable from the first test.

## Phase Order

1. **Contracts First**: request, snapshot, envelope, policies, router errors.
2. **State Surfaces**: tool registry, module registry, snapshot builder.
3. **Resolution Logic**: local routing pipeline, command fix engine, clarification thresholds.
4. **Runtime Integration**: runtime wiring, CLI entrypoints, events, optional escalation boundaries.
5. **Hardening And Handoff**: contract suite, docs, migration note for Rust + TypeScript + Tauri.

## Phase 1: Contracts First

### Task 1: Add TerminalRequest, RegistrySnapshot, And Route Envelope Models

**Files:**
- Create: `src/local_ai_agent/router/__init__.py`
- Create: `src/local_ai_agent/router/request.py`
- Create: `src/local_ai_agent/router/snapshot.py`
- Create: `src/local_ai_agent/router/output.py`
- Test: `tests/test_router_contracts.py`

**Step 1: Write the failing test**

```python
from local_ai_agent.router.request import TerminalRequest
from local_ai_agent.router.snapshot import RegistrySnapshot
from local_ai_agent.router.output import RouteEnvelope


def test_router_contract_models_round_trip_minimal_json():
    request = TerminalRequest(
        request_id="req-1",
        session_id="sess-1",
        shell="powershell",
        raw_input="gh --version",
        cwd="C:\\repo",
        snapshot_version="snap-1",
    )
    snapshot = RegistrySnapshot.minimal(
        snapshot_version="snap-1",
        built_for_session="sess-1",
    )
    envelope = RouteEnvelope.command_fix(
        intent="correction",
        snapshot_version="snap-1",
        original="github.cli --version",
        suggested_command="gh --version",
        evidence=["alias_match:gh"],
        confidence=0.92,
        threshold_applied=0.90,
        threshold_source="intent:command_fix",
        resolver_path=["normalize_input", "resolve_local_candidates"],
    )

    assert request.snapshot_version == snapshot.snapshot_version
    assert envelope.route == "command_fix"
    assert envelope.payload["suggested_command"] == "gh --version"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_router_contracts.py -v`
Expected: FAIL with `ModuleNotFoundError` for `local_ai_agent.router`

**Step 3: Write minimal implementation**

```python
@dataclass(slots=True)
class TerminalRequest:
    request_id: str
    session_id: str
    shell: Literal["powershell", "bash"]
    raw_input: str
    cwd: str
    snapshot_version: str
    env_visible: dict[str, str] = field(default_factory=dict)
    recent_history: list[str] = field(default_factory=list)
    ui_context: dict[str, str] = field(default_factory=dict)
    requested_mode: Literal["strict", "interactive", "headless"] = "strict"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_router_contracts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/router/__init__.py src/local_ai_agent/router/request.py src/local_ai_agent/router/snapshot.py src/local_ai_agent/router/output.py tests/test_router_contracts.py
git commit -m "feat: add deterministic router contracts"
```

### Task 2: Add Policies, Thresholds, And Router Error Envelope

**Files:**
- Create: `src/local_ai_agent/router/policies.py`
- Create: `src/local_ai_agent/router/errors.py`
- Modify: `src/local_ai_agent/router/output.py`
- Test: `tests/test_router_policies.py`

**Step 1: Write the failing test**

```python
from local_ai_agent.router.errors import RouterErrorEnvelope
from local_ai_agent.router.policies import ConfidencePolicy, PolicyMaterialization


def test_policy_overrides_and_router_error_are_serializable():
    thresholds = ConfidencePolicy.defaults()
    policies = PolicyMaterialization.empty()
    error = RouterErrorEnvelope(
        error_code="snapshot_version_mismatch",
        request_id="req-1",
        session_id="sess-1",
        snapshot_version="snap-1",
        diagnostics={"stage": "snapshot_binding"},
    )

    assert thresholds.for_intent("execution") == 0.93
    assert "trust_policy" in policies.model_dump()
    assert error.kind == "router_error"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_router_policies.py -v`
Expected: FAIL because policy and error modules do not exist

**Step 3: Write minimal implementation**

```python
class ConfidencePolicy(BaseModel):
    global_auto_accept: float = 0.90
    by_intent: dict[str, float] = Field(
        default_factory=lambda: {
            "execution": 0.93,
            "correction": 0.90,
            "installation": 0.85,
        }
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_router_policies.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/router/policies.py src/local_ai_agent/router/errors.py src/local_ai_agent/router/output.py tests/test_router_policies.py
git commit -m "feat: add router policies and typed errors"
```

## Phase 2: State Surfaces

### Task 3: Add ToolAdapter Contracts And ToolRegistry Snapshot Inputs

**Files:**
- Create: `src/local_ai_agent/tools/__init__.py`
- Create: `src/local_ai_agent/tools/contracts.py`
- Create: `src/local_ai_agent/tools/registry.py`
- Create: `src/local_ai_agent/tools/adapters/__init__.py`
- Create: `src/local_ai_agent/tools/adapters/generic_cli.py`
- Create: `src/local_ai_agent/tools/adapters/bash.py`
- Create: `src/local_ai_agent/tools/adapters/powershell.py`
- Test: `tests/test_tool_registry.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from local_ai_agent.tools.adapters.generic_cli import GenericCliToolAdapter
from local_ai_agent.tools.registry import ToolRegistry


def test_tool_registry_only_exports_validated_available_tools():
    registry = ToolRegistry()
    registry.register(
        tool_name="gh",
        adapter=GenericCliToolAdapter(shell="powershell"),
        binary_path=Path("C:/tools/gh.exe"),
        aliases=["github", "github-cli"],
        capabilities=["version"],
        available=True,
    )

    snapshot_tools = registry.snapshot_tools()

    assert snapshot_tools[0]["tool_name"] == "gh"
    assert snapshot_tools[0]["available"] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_tool_registry.py -v`
Expected: FAIL because tool registry package does not exist

**Step 3: Write minimal implementation**

```python
@dataclass(slots=True)
class ToolSpec:
    tool_name: str
    adapter_name: str
    shell: str
    binary_path: Path
    aliases: list[str]
    capabilities: list[str]
    available: bool
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_tool_registry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/tools src/local_ai_agent/tools/adapters tests/test_tool_registry.py
git commit -m "feat: add tool registry and adapter contracts"
```

### Task 4: Add ModuleRegistry And RegistrySnapshot Builder

**Files:**
- Create: `src/local_ai_agent/modules/__init__.py`
- Create: `src/local_ai_agent/modules/manifest.py`
- Create: `src/local_ai_agent/modules/registry.py`
- Create: `src/local_ai_agent/modules/snapshot_builder.py`
- Modify: `src/local_ai_agent/router/snapshot.py`
- Test: `tests/test_module_registry.py`

**Step 1: Write the failing test**

```python
from local_ai_agent.modules.manifest import ModuleManifest
from local_ai_agent.modules.registry import ModuleRegistry
from local_ai_agent.modules.snapshot_builder import build_registry_snapshot
from local_ai_agent.tools.registry import ToolRegistry


def test_snapshot_builder_materializes_tools_modules_and_typed_extensions():
    module_registry = ModuleRegistry()
    tool_registry = ToolRegistry()
    module_registry.register(
        ModuleManifest(
            module_id="mcp-context7",
            module_type="adapter",
            version="1.0.0",
            enabled=True,
            capabilities=["docs_lookup"],
        )
    )

    snapshot = build_registry_snapshot(
        session_id="sess-1",
        tool_registry=tool_registry,
        module_registry=module_registry,
    )

    assert snapshot.built_for_session == "sess-1"
    assert "policies" in snapshot.extensions
    assert "docs_lookup" in snapshot.capability_surface["capabilities"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_module_registry.py -v`
Expected: FAIL because module registry and snapshot builder do not exist

**Step 3: Write minimal implementation**

```python
def build_registry_snapshot(*, session_id: str, tool_registry: ToolRegistry, module_registry: ModuleRegistry) -> RegistrySnapshot:
    return RegistrySnapshot(
        snapshot_version="generated",
        built_at=datetime.now(timezone.utc).isoformat(),
        built_for_session=session_id,
        source_versions={"tool_registry": tool_registry.version, "module_registry": module_registry.version},
        execution_surface={"tools": tool_registry.snapshot_tools()},
        capability_surface=module_registry.snapshot_capabilities(),
        extensions=typed_empty_extensions(),
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_module_registry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/modules src/local_ai_agent/router/snapshot.py tests/test_module_registry.py
git commit -m "feat: add module registry and snapshot builder"
```

## Phase 3: Resolution Logic

### Task 5: Implement Local-Only Router Pipeline Skeleton

**Files:**
- Create: `src/local_ai_agent/router/classifier.py`
- Create: `src/local_ai_agent/router/pipeline.py`
- Modify: `src/local_ai_agent/router/output.py`
- Test: `tests/test_router_pipeline.py`

**Step 1: Write the failing test**

```python
from local_ai_agent.router.pipeline import DeterministicRouter
from local_ai_agent.router.request import TerminalRequest
from local_ai_agent.router.snapshot import RegistrySnapshot


def test_router_emits_tool_execution_using_snapshot_only():
    snapshot = RegistrySnapshot.minimal(
        snapshot_version="snap-1",
        built_for_session="sess-1",
        tools=[
            {
                "tool_name": "gh",
                "adapter": "generic_cli",
                "shell": "powershell",
                "command_policy": "local_or_global",
                "available": True,
                "aliases": ["github"],
                "capabilities": ["version"],
            }
        ],
        capabilities=["tool_execution", "command_fix"],
    )
    router = DeterministicRouter()
    request = TerminalRequest(
        request_id="req-1",
        session_id="sess-1",
        shell="powershell",
        raw_input="gh --version",
        cwd="C:\\repo",
        snapshot_version="snap-1",
    )

    result = router.resolve(request, snapshot)

    assert result.route == "tool_execution"
    assert result.resolver_path == [
        "normalize_input",
        "parse_command_shape",
        "classify_intent",
        "resolve_local_candidates",
        "apply_deterministic_rules",
        "evaluate_confidence",
    ]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_router_pipeline.py -v`
Expected: FAIL because `DeterministicRouter` does not exist

**Step 3: Write minimal implementation**

```python
class DeterministicRouter:
    def resolve(self, request: TerminalRequest, snapshot: RegistrySnapshot) -> RouteEnvelope:
        if request.snapshot_version != snapshot.snapshot_version:
            raise SnapshotVersionMismatchError(...)
        return self._resolve_local_only(request, snapshot)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_router_pipeline.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/router/classifier.py src/local_ai_agent/router/pipeline.py src/local_ai_agent/router/output.py tests/test_router_pipeline.py
git commit -m "feat: add deterministic router pipeline"
```

### Task 6: Implement CommandFix Engine And Clarification Thresholds

**Files:**
- Create: `src/local_ai_agent/router/fixes.py`
- Modify: `src/local_ai_agent/router/pipeline.py`
- Modify: `src/local_ai_agent/router/policies.py`
- Test: `tests/test_command_fix.py`

**Step 1: Write the failing test**

```python
from local_ai_agent.router.fixes import CommandFixEngine


def test_command_fix_degrades_to_clarification_when_multiple_candidates_tie():
    engine = CommandFixEngine()
    result = engine.build_fix(
        raw_input="git.cli --version",
        tools=[
            {"tool_name": "git", "aliases": ["git-cli"]},
            {"tool_name": "gh", "aliases": ["github-cli"]},
        ],
        threshold=0.90,
    )

    assert result.route == "clarification"
    assert len(result.payload["options"]) == 2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_command_fix.py -v`
Expected: FAIL because command fix engine does not exist

**Step 3: Write minimal implementation**

```python
class CommandFixEngine:
    def build_fix(self, *, raw_input: str, tools: list[dict[str, object]], threshold: float) -> RouteEnvelope:
        ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_command_fix.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/router/fixes.py src/local_ai_agent/router/pipeline.py src/local_ai_agent/router/policies.py tests/test_command_fix.py
git commit -m "feat: add command fix engine and clarification thresholds"
```

## Phase 4: Runtime Integration

### Task 7: Wire Router Runtime, Snapshot Binding, And Router Events

**Files:**
- Create: `src/local_ai_agent/router/events.py`
- Modify: `src/local_ai_agent/runtime.py`
- Modify: `src/local_ai_agent/session_runner.py`
- Modify: `src/local_ai_agent/contracts.py`
- Test: `tests/test_router_integration.py`
- Test: `tests/test_router_events.py`

**Step 1: Write the failing test**

```python
def test_runtime_binds_request_to_single_snapshot_and_emits_events():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_router_integration.py tests/test_router_events.py -v`
Expected: FAIL because runtime has no router wiring or event sink

**Step 3: Write minimal implementation**

```python
@dataclass(slots=True)
class RouterRuntime:
    router: DeterministicRouter
    snapshot_provider: SnapshotProvider
    event_sink: RouterEventSink
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_router_integration.py tests/test_router_events.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/router/events.py src/local_ai_agent/runtime.py src/local_ai_agent/session_runner.py src/local_ai_agent/contracts.py tests/test_router_integration.py tests/test_router_events.py
git commit -m "feat: wire router runtime and event emission"
```

### Task 8: Add Hub Proposals And AiAssist Delegation Boundaries

**Files:**
- Create: `src/local_ai_agent/hub/__init__.py`
- Create: `src/local_ai_agent/hub/proposals.py`
- Create: `src/local_ai_agent/router/escalation.py`
- Modify: `src/local_ai_agent/router/pipeline.py`
- Modify: `src/local_ai_agent/router/output.py`
- Test: `tests/test_router_escalation.py`

**Step 1: Write the failing test**

```python
def test_router_returns_hub_install_when_required_capability_is_missing():
    ...


def test_router_denies_ai_escalation_when_policy_blocks_external_execution():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_router_escalation.py -v`
Expected: FAIL because Hub proposals and escalation guardrails do not exist

**Step 3: Write minimal implementation**

```python
class EscalationPlanner:
    def plan(self, *, intent: str, snapshot: RegistrySnapshot) -> RouteEnvelope:
        ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_router_escalation.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/hub src/local_ai_agent/router/escalation.py src/local_ai_agent/router/pipeline.py src/local_ai_agent/router/output.py tests/test_router_escalation.py
git commit -m "feat: add hub proposals and external escalation boundaries"
```

## Phase 5: Hardening And Handoff

### Task 9: Extend CLI Surface For Routing-Only Middleware Mode

**Files:**
- Modify: `src/local_ai_agent/cli.py`
- Modify: `src/local_ai_agent/runtime.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
def test_cli_route_command_prints_machine_readable_router_json():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_cli_route_command_prints_machine_readable_router_json -v`
Expected: FAIL because CLI has no routing-only command

**Step 3: Write minimal implementation**

```python
route = subparsers.add_parser("route", help="Resolve terminal input into a JSON routing decision.")
route.add_argument("--text", required=True)
route.add_argument("--shell", choices=["powershell", "bash"], required=True)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_cli_route_command_prints_machine_readable_router_json -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/local_ai_agent/cli.py src/local_ai_agent/runtime.py tests/test_cli.py
git commit -m "feat: add routing-only cli mode"
```

### Task 10: Verify Contract Invariants, Update Docs, And Record Future Migration

**Files:**
- Create: `tests/test_router_contract_invariants.py`
- Modify: `README.md`
- Modify: `docs/plans/2026-04-16-deterministic-terminal-middleware-implementation.md`

**Step 1: Write the failing test**

```python
def test_router_contract_invariants_hold_for_local_fix_and_reject_routes():
    ...
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_router_contract_invariants.py -v`
Expected: FAIL because invariant suite does not exist

**Step 3: Write minimal implementation**

```python
def assert_semantic_command_match(command: str, argv: list[str]) -> None:
    ...
```

**Step 4: Run focused suite and update docs**

Run: `pytest tests/test_router_contracts.py tests/test_router_policies.py tests/test_tool_registry.py tests/test_module_registry.py tests/test_router_pipeline.py tests/test_command_fix.py tests/test_router_integration.py tests/test_router_events.py tests/test_router_escalation.py tests/test_router_contract_invariants.py -v`
Expected: PASS

Update `README.md` with:
- middleware purpose and non-goals
- JSON-only output contract
- `route` CLI workflow
- reference-repo policy

Add a final section to this plan recording the already-agreed future migration:
- Python is the implementation stack for the current middleware phases
- Rust + TypeScript + Tauri is the agreed definitive stack after Python behavior is complete and validated
- the migration is future scope, not an open design decision

**Step 5: Commit**

```bash
git add tests/test_router_contract_invariants.py README.md docs/plans/2026-04-16-deterministic-terminal-middleware-implementation.md
git commit -m "docs: verify router invariants and record migration path"
```

## Agreed Future Migration

- The current implementation plan targets `Python` to preserve continuity with the existing repository and to validate behavior quickly against the deterministic core.
- The definitive product stack is already agreed as `Rust + TypeScript + Tauri`.
- That migration is a later phase after the Python middleware is complete, tested, and behaviorally stable.
- This migration is recorded here to prevent reopening the language/runtime discussion during Python implementation tasks.
- That future migration is a closed later phase, not an open decision within the current Python middleware plan.

## Suggested Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6
7. Task 7
8. Task 8
9. Task 9
10. Task 10

## Out Of Scope During This Plan

- Rewriting the runtime in Rust before the Python contracts are proven.
- Importing or embedding execution logic from `Claudia`, `DEV-OS`, `AsistenteW11`, or `AsistHub`.
- Giving the router authority to execute subprocesses or install modules.
- Modifying `src/local_ai_agent/agent.py`.
