# Rust + TypeScript + Tauri Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current Python-first runtime with a contract-compatible Rust core and a TypeScript MCP sidecar without breaking the working CLI and middleware flow during transition, while keeping the Tauri desktop UI as an optional Hub-installed module rather than a required product surface.

**Architecture:** Migrate in narrow, testable slices. Rust becomes the system of record for deterministic routing, terminal mediation, runtime state, and the primary CLI/middleware product surface; a standalone TypeScript sidecar owns MCP connectivity; the Tauri frontend is a separate optional Hub module that, when installed, provides a React desktop UI surface for users who want it while still talking only to Rust. Python stays in place until each replacement passes equivalent fixtures, contract checks, and end-to-end parity.

**Tech Stack:** Rust stable + Cargo workspace, Tauri 2, TypeScript 5, Node.js LTS, React, TanStack Router, TanStack Query, Vite, Vitest, FastMCP, Sileo, React Doctor, Unlighthouse, JSON-RPC 2.0 over stdio, existing Python 3.11 test suite, `pytest`

---

## Implementation Rules

- Do not remove or rewrite active Python behavior before parity is proven for the same contract surface.
- Keep the existing PowerShell middleware contract stable: `route` returns JSON only, `exec --json` returns JSON only, `exec` owns interactive execution UX.
- Treat the TypeScript MCP sidecar as an external process boundary, not a library imported into Rust or the frontend.
- Keep the Tauri frontend focused on presentation and interaction orchestration: it renders state, manages navigation/query state, and invokes Rust commands/events only.
- Prefer additive implementation in new top-level directories: `crates/`, `services/`, `apps/`, `tests/contracts/`.
- Preserve the current Python tests as migration blockers until equivalent Rust/TS/Tauri coverage exists.
- Use JSON as the only cross-process payload format and version every externally visible contract.
- Treat the CLI and PowerShell middleware as the primary product; the system must remain fully functional without Tauri installed.
- Treat the Tauri UI as an optional Hub module that users install explicitly, just like other optional modules.
- Treat `Caveman` as an execution convention for repetitive technical tasks: short, dense progress/result wording when the implementation phase begins.
- Treat `Fontpair` and Google `Stitch` as design references only, not runtime dependencies.
- Document `React Email` for future logging-by-email and authentication workflows, but do not make it part of the initial migration critical path.

## Frontend Stack Decision

- Use `React + TanStack Router + TanStack Query + Vite` inside the Tauri app.
- Treat this frontend as an optional Hub module that provides a desktop UI surface for users who want it.
- The React + TanStack complexity is justified for the UI module when it exists, but it does not define the identity of the system.
- Do not use Svelte as the default: the UI scope now justifies React's broader ecosystem, routing model, and debugging surface.
- Do not use Vue as the default: it remains viable, but the requested toolchain and expected UI complexity align better with React.
- Do not treat `Vite` as an alternative to React: `Vite` is the build tool and dev server for the chosen React stack.
- Do not treat `TanStack` as a React replacement: `TanStack Router` and `TanStack Query` are support libraries inside the React app.

## Frontend Library Guidance

- Start with React function components, Tauri command wrappers, `TanStack Router` for app structure, and `TanStack Query` for command/query cache orchestration.
- Add `Sileo` for toast-style notifications around command status, tool failures, sidecar health, and terminal preview outcomes.
- Use `React Doctor` during development to catch common React anti-patterns before the desktop app grows complex.
- Run `Unlighthouse` only after the main React/Tauri screens exist in Phase 7; treat it as an audit tool, not as a gate for earlier backend phases.
- Use `Fontpair` as a typography decision reference when defining the Phase 7 visual system.
- Use Google `Stitch` as a personal design-aid during Phase 7 iteration, but keep it out of the dependency graph and build pipeline.
- Document `React Email` as a future integration option for email-based logging summaries and authentication flows; do not wire it into the first migration cut.

## Supplementary Tooling Decisions

- `FastMCP` is the default way to reduce boilerplate in the TypeScript sidecar when building first-party MCP adapters.
- `Sileo` is the UI notification layer inside the React frontend.
- `React Doctor` is a development-time diagnostic aid for React quality.
- `Unlighthouse` is a late-phase audit tool once the Tauri UI is assembled.
- `Fontpair` and Google `Stitch` guide design choices but never ship in production.
- `Caveman` is an execution convention for concise technical updates during repetitive implementation work.
- `React Email` is documented now for future integrations, not implemented in the migration MVP.
- The Hub is the installation mechanism for the optional desktop UI module.

## Phase Order

1. **Contracts And Parity Harness**: freeze payloads and collect golden fixtures from Python.
2. **Rust Workspace And CLI Skeleton**: stand up crates and parity-oriented CLI contracts.
3. **Rust Router Migration**: move deterministic routing first.
4. **Rust Terminal Migration**: move execution mediation and middleware compatibility next.
5. **TypeScript MCP Sidecar**: add the isolated MCP process and Rust bridge.
6. **Rust Session Runtime Migration**: move chat/reply orchestration and local state.
7. **Optional Hub UI Module With React**: add the desktop UI as an installable Hub extension after core runtime surfaces are stable.
8. **Core Rust Cutover And Python Retirement**: switch CLI and middleware defaults only after parity evidence is complete.

## Phase 1: Contracts And Parity Harness

### Task 1: Freeze Machine-Readable Contracts And Export Golden Fixtures

**Files:**
- Create: `tests/contracts/README.md`
- Create: `tests/contracts/router/`
- Create: `tests/contracts/terminal/`
- Create: `tests/contracts/runtime/`
- Create: `scripts/export_contract_fixtures.py`
- Modify: `docs/architecture/migration-to-rust-ts-tauri.md`
- Test: `tests/test_session_runner.py`
- Test: `tests/test_runtime_router_wiring.py`

**Step 1: Write the failing test**

```python
from pathlib import Path


def test_contract_fixture_directories_exist():
    assert Path("tests/contracts/router").exists()
    assert Path("tests/contracts/terminal").exists()
    assert Path("tests/contracts/runtime").exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_contract_fixtures_layout.py -v`
Expected: FAIL because fixture directories and layout test do not exist

**Step 3: Write minimal implementation**

```python
from pathlib import Path


def test_contract_fixture_directories_exist():
    assert Path("tests/contracts/router").exists()
    assert Path("tests/contracts/terminal").exists()
    assert Path("tests/contracts/runtime").exists()
```

Create the directories and add a `README.md` that explains the source of truth and naming convention for exported fixtures.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_contract_fixtures_layout.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/contracts scripts/export_contract_fixtures.py docs/architecture/migration-to-rust-ts-tauri.md tests/test_contract_fixtures_layout.py
git commit -m "test: add contract fixture harness for migration"
```

### Task 2: Export Python Golden Fixtures For Route, Exec, Reply, And Chat

**Files:**
- Modify: `scripts/export_contract_fixtures.py`
- Create: `tests/contracts/router/*.json`
- Create: `tests/contracts/terminal/*.json`
- Create: `tests/contracts/runtime/*.json`
- Test: `tests/test_contract_fixtures_export.py`

**Step 1: Write the failing test**

```python
from pathlib import Path


def test_exported_router_fixtures_are_present():
    fixtures = list(Path("tests/contracts/router").glob("*.json"))
    assert fixtures
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_contract_fixtures_export.py -v`
Expected: FAIL because no fixture export exists yet

**Step 3: Write minimal implementation**

```python
import json
from pathlib import Path


def write_fixture(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

Expand the exporter to write representative payloads captured from the current Python runtime for:

- router envelopes,
- router error envelopes,
- `exec --json`,
- session reply outputs,
- chat transcripts,
- middleware-compatible examples.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_contract_fixtures_export.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/export_contract_fixtures.py tests/contracts tests/test_contract_fixtures_export.py
git commit -m "test: export golden fixtures from python runtime"
```

## Phase 2: Rust Workspace And CLI Skeleton

### Task 3: Create The Rust Workspace Skeleton

**Files:**
- Create: `Cargo.toml`
- Create: `crates/core-contracts/Cargo.toml`
- Create: `crates/core-contracts/src/lib.rs`
- Create: `crates/router-core/Cargo.toml`
- Create: `crates/router-core/src/lib.rs`
- Create: `crates/terminal-core/Cargo.toml`
- Create: `crates/terminal-core/src/lib.rs`
- Create: `crates/runtime-core/Cargo.toml`
- Create: `crates/runtime-core/src/lib.rs`
- Create: `crates/cli-app/Cargo.toml`
- Create: `crates/cli-app/src/main.rs`
- Test: `crates/core-contracts/tests/contracts_smoke.rs`

**Step 1: Write the failing test**

```rust
#[test]
fn workspace_smoke_builds() {
    assert!(true);
}
```

**Step 2: Run test to verify it fails**

Run: `cargo test -p core-contracts`
Expected: FAIL because the workspace and crate do not exist

**Step 3: Write minimal implementation**

```rust
pub const CONTRACTS_VERSION: &str = "0.1.0";
```

Create the workspace and minimal crates with no behavior beyond a compilable scaffold.

**Step 4: Run test to verify it passes**

Run: `cargo test -p core-contracts`
Expected: PASS

**Step 5: Commit**

```bash
git add Cargo.toml crates
git commit -m "chore: add rust workspace skeleton"
```

### Task 4: Mirror Canonical Contract Types In Rust

**Files:**
- Modify: `crates/core-contracts/src/lib.rs`
- Create: `crates/core-contracts/src/router.rs`
- Create: `crates/core-contracts/src/terminal.rs`
- Create: `crates/core-contracts/src/runtime.rs`
- Test: `crates/core-contracts/tests/serialization_parity.rs`
- Test: `tests/contracts/router/*.json`

**Step 1: Write the failing test**

```rust
#[test]
fn route_envelope_deserializes_from_python_fixture() {
    let raw = include_str!("../../../tests/contracts/router/command_fix.json");
    let parsed: serde_json::Value = serde_json::from_str(raw).unwrap();
    assert_eq!(parsed["kind"], "route");
}
```

**Step 2: Run test to verify it fails**

Run: `cargo test -p core-contracts serialization_parity`
Expected: FAIL because typed contract modules do not exist

**Step 3: Write minimal implementation**

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct RouteEnvelope {
    pub kind: String,
    pub snapshot_version: String,
    pub route: String,
}
```

Add Rust types that can deserialize the exported Python fixtures without losing required fields.

**Step 4: Run test to verify it passes**

Run: `cargo test -p core-contracts serialization_parity`
Expected: PASS

**Step 5: Commit**

```bash
git add crates/core-contracts tests/contracts
git commit -m "feat: mirror python contracts in rust"
```

### Task 5: Add A Rust CLI That Can Emit Contract-Shaped Stub Output

**Files:**
- Modify: `crates/cli-app/src/main.rs`
- Create: `crates/cli-app/src/commands.rs`
- Test: `crates/cli-app/tests/cli_contracts.rs`

**Step 1: Write the failing test**

```rust
#[test]
fn route_command_returns_json() {
    let output = std::process::Command::new(env!("CARGO_BIN_EXE_cli-app"))
        .args(["route", "--fixture", "command_fix"])
        .output()
        .unwrap();
    let stdout = String::from_utf8(output.stdout).unwrap();
    assert!(stdout.contains("\"route\""));
}
```

**Step 2: Run test to verify it fails**

Run: `cargo test -p cli-app cli_contracts`
Expected: FAIL because the CLI does not support contract-shaped output

**Step 3: Write minimal implementation**

```rust
fn main() {
    println!("{{\"kind\":\"route\",\"route\":\"command_fix\"}}");
}
```

Wire placeholder commands for `route`, `exec`, `reply`, and `chat` that emit valid JSON stubs using the Rust contract types.

**Step 4: Run test to verify it passes**

Run: `cargo test -p cli-app cli_contracts`
Expected: PASS

**Step 5: Commit**

```bash
git add crates/cli-app
git commit -m "feat: add rust cli contract skeleton"
```

## Phase 3: Rust Router Migration

### Task 6: Port Registry Snapshot Inputs To Rust

**Files:**
- Create: `crates/router-core/src/snapshot.rs`
- Create: `crates/router-core/src/registry.rs`
- Test: `crates/router-core/tests/snapshot_parity.rs`
- Reference: `src/local_ai_agent/modules/snapshot_builder.py`
- Reference: `src/local_ai_agent/tools/registry.py`

**Step 1: Write the failing test**

```rust
#[test]
fn registry_snapshot_matches_fixture_shape() {
    let raw = include_str!("../../../tests/contracts/router/snapshot_minimal.json");
    let parsed: serde_json::Value = serde_json::from_str(raw).unwrap();
    assert!(parsed.get("snapshot_version").is_some());
}
```

**Step 2: Run test to verify it fails**

Run: `cargo test -p router-core snapshot_parity`
Expected: FAIL because snapshot support does not exist

**Step 3: Write minimal implementation**

```rust
pub struct RegistrySnapshot {
    pub snapshot_version: String,
}
```

Port the minimal snapshot shape first, then fill in tool/module fields only after the tests require them.

**Step 4: Run test to verify it passes**

Run: `cargo test -p router-core snapshot_parity`
Expected: PASS

**Step 5: Commit**

```bash
git add crates/router-core
git commit -m "feat: add rust registry snapshot model"
```

### Task 7: Port Deterministic Router Classification And Envelope Resolution

**Files:**
- Create: `crates/router-core/src/classifier.rs`
- Create: `crates/router-core/src/pipeline.rs`
- Create: `crates/router-core/src/errors.rs`
- Modify: `crates/router-core/src/lib.rs`
- Test: `crates/router-core/tests/router_parity.rs`
- Reference: `src/local_ai_agent/router/classifier.py`
- Reference: `src/local_ai_agent/router/pipeline.py`
- Reference: `src/local_ai_agent/router/output.py`

**Step 1: Write the failing test**

```rust
#[test]
fn command_fix_fixture_resolves_to_command_fix_route() {
    assert_eq!("command_fix", "todo");
}
```

**Step 2: Run test to verify it fails**

Run: `cargo test -p router-core router_parity`
Expected: FAIL because the router logic has not been ported

**Step 3: Write minimal implementation**

```rust
pub fn resolve_fixture_route() -> &'static str {
    "command_fix"
}
```

Port the router in the same order as the Python code:

- normalization,
- candidate resolution,
- confidence thresholds,
- route envelope emission,
- router error envelope emission.

**Step 4: Run test to verify it passes**

Run: `cargo test -p router-core router_parity`
Expected: PASS

**Step 5: Commit**

```bash
git add crates/router-core
git commit -m "feat: port deterministic router to rust"
```

### Task 8: Swap Rust `route` Behind A Parity Flag

**Files:**
- Modify: `crates/cli-app/src/commands.rs`
- Modify: `README.md`
- Test: `crates/cli-app/tests/route_command_parity.rs`
- Test: `tests/test_powershell_middleware.py`

**Step 1: Write the failing test**

```rust
#[test]
fn route_command_can_use_rust_backend_flag() {
    assert!(std::env::var("COPILOTTRAE_ROUTE_BACKEND").is_err());
}
```

**Step 2: Run test to verify it fails**

Run: `cargo test -p cli-app route_command_parity`
Expected: FAIL because backend selection is not implemented

**Step 3: Write minimal implementation**

```rust
let backend = std::env::var("COPILOTTRAE_ROUTE_BACKEND").unwrap_or_else(|_| "python".into());
```

Support a backend-selection flag or env var so parity can be validated without changing the default path.

**Step 4: Run test to verify it passes**

Run: `cargo test -p cli-app route_command_parity`
Expected: PASS

**Step 5: Commit**

```bash
git add crates/cli-app README.md
git commit -m "feat: add rust route backend selection"
```

## Phase 4: Rust Terminal Migration

### Task 9: Port Terminal Preview, Trust Policy, And Empty-Command Guardrails

**Files:**
- Create: `crates/terminal-core/src/host.rs`
- Create: `crates/terminal-core/src/policy.rs`
- Modify: `crates/terminal-core/src/lib.rs`
- Test: `crates/terminal-core/tests/terminal_preview_parity.rs`
- Reference: `src/local_ai_agent/terminal/host.py`
- Reference: `tests/test_terminal_host.py`

**Step 1: Write the failing test**

```rust
#[test]
fn empty_command_is_rejected() {
    assert!(false, "port host validation");
}
```

**Step 2: Run test to verify it fails**

Run: `cargo test -p terminal-core terminal_preview_parity`
Expected: FAIL because host validation logic is not implemented

**Step 3: Write minimal implementation**

```rust
pub fn validate_command(raw: &str) -> Result<(), &'static str> {
    if raw.trim().is_empty() {
        return Err("empty_command");
    }
    Ok(())
}
```

Add preview-only validation before any subprocess execution support is introduced.

**Step 4: Run test to verify it passes**

Run: `cargo test -p terminal-core terminal_preview_parity`
Expected: PASS

**Step 5: Commit**

```bash
git add crates/terminal-core
git commit -m "feat: port terminal preview guardrails"
```

### Task 10: Port Execution Mediation And JSON Output For `exec --json`

**Files:**
- Modify: `crates/terminal-core/src/host.rs`
- Modify: `crates/cli-app/src/commands.rs`
- Test: `crates/cli-app/tests/exec_json_parity.rs`
- Test: `tests/test_terminal_integration.py`
- Test: `tests/test_powershell_middleware.py`

**Step 1: Write the failing test**

```rust
#[test]
fn exec_json_emits_route_envelope_without_running_command() {
    assert!(false, "needs preview envelope parity");
}
```

**Step 2: Run test to verify it fails**

Run: `cargo test -p cli-app exec_json_parity`
Expected: FAIL because `exec --json` parity is not implemented

**Step 3: Write minimal implementation**

```rust
println!("{{\"kind\":\"route\",\"route\":\"local_exec\"}}");
```

Match Python behavior exactly for preview mode before introducing actual execution side effects.

**Step 4: Run test to verify it passes**

Run: `cargo test -p cli-app exec_json_parity`
Expected: PASS

**Step 5: Commit**

```bash
git add crates/terminal-core crates/cli-app
git commit -m "feat: add rust exec json parity"
```

### Task 11: Validate PowerShell Middleware Against The Rust CLI

**Files:**
- Modify: `scripts/powershell/middleware.ps1`
- Modify: `README.md`
- Test: `tests/test_powershell_middleware.py`
- Test: `tests/test_real_terminal_usage.py`

**Step 1: Write the failing test**

```python
def test_middleware_can_target_rust_cli_backend():
    assert False, "wire middleware backend switch"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_powershell_middleware.py -v`
Expected: FAIL because the middleware cannot target the Rust CLI yet

**Step 3: Write minimal implementation**

```powershell
$Backend = $env:COPILOTTRAE_CLI_BACKEND
if (-not $Backend) { $Backend = "python" }
```

Add an explicit backend switch so the middleware can validate Rust in real usage before default cutover.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_powershell_middleware.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/powershell/middleware.ps1 README.md tests/test_powershell_middleware.py
git commit -m "feat: add middleware backend switch for rust cli"
```

## Phase 5: TypeScript MCP Sidecar

### Task 12: Create The MCP Sidecar Workspace

**Files:**
- Create: `services/mcp-sidecar/package.json`
- Create: `services/mcp-sidecar/tsconfig.json`
- Create: `services/mcp-sidecar/src/index.ts`
- Create: `services/mcp-sidecar/src/protocol.ts`
- Create: `services/mcp-sidecar/src/server.ts`
- Create: `services/mcp-sidecar/vitest.config.ts`
- Create: `services/mcp-sidecar/tests/health.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";

describe("sidecar health", () => {
  it("reports ready", () => {
    expect(false).toBe(true);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix services/mcp-sidecar test`
Expected: FAIL because the sidecar workspace does not exist

**Step 3: Write minimal implementation**

```ts
export function health() {
  return { ok: true };
}
```

Use plain Node + TypeScript plus `FastMCP` first; do not add web framework abstractions inside the sidecar.

**Step 4: Run test to verify it passes**

Run: `npm --prefix services/mcp-sidecar test`
Expected: PASS

**Step 5: Commit**

```bash
git add services/mcp-sidecar
git commit -m "chore: add typescript mcp sidecar skeleton"
```

### Task 13: Implement JSON-RPC 2.0 Stdio Bridge In The Sidecar

**Files:**
- Modify: `services/mcp-sidecar/src/index.ts`
- Modify: `services/mcp-sidecar/src/protocol.ts`
- Create: `services/mcp-sidecar/src/stdio.ts`
- Create: `services/mcp-sidecar/tests/protocol.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";

describe("protocol", () => {
  it("parses a json-rpc request", () => {
    expect(typeof undefined).toBe("object");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix services/mcp-sidecar test`
Expected: FAIL because JSON-RPC transport parsing is missing

**Step 3: Write minimal implementation**

```ts
export type JsonRpcRequest = {
  jsonrpc: "2.0";
  id: string | number;
  method: string;
  params?: Record<string, unknown>;
};
```

Support requests, responses, and notifications over stdio with strict shape validation.

**Step 4: Run test to verify it passes**

Run: `npm --prefix services/mcp-sidecar test`
Expected: PASS

**Step 5: Commit**

```bash
git add services/mcp-sidecar
git commit -m "feat: add json-rpc stdio bridge to mcp sidecar"
```

### Task 14: Add MCP Server Adapters For Context7, Playwright, And Brave Search With FastMCP

**Files:**
- Create: `services/mcp-sidecar/src/servers/context7.ts`
- Create: `services/mcp-sidecar/src/servers/playwright.ts`
- Create: `services/mcp-sidecar/src/servers/brave.ts`
- Create: `services/mcp-sidecar/src/servers/registry.ts`
- Modify: `services/mcp-sidecar/src/server.ts`
- Create: `services/mcp-sidecar/tests/servers.test.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";

describe("server registry", () => {
  it("lists configured mcp servers", () => {
    expect([]).toContain("context7");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix services/mcp-sidecar test`
Expected: FAIL because no server adapters are registered

**Step 3: Write minimal implementation**

```ts
export const configuredServers = ["context7", "playwright", "brave-search"] as const;
```

Port one adapter at a time and keep each adapter independently testable with mocked transport boundaries. Use `FastMCP` to define tool/resource surfaces with less custom protocol boilerplate.

**Step 4: Run test to verify it passes**

Run: `npm --prefix services/mcp-sidecar test`
Expected: PASS

**Step 5: Commit**

```bash
git add services/mcp-sidecar
git commit -m "feat: add mcp sidecar server adapters"
```

### Task 15: Add Rust-Side Sidecar Client And Health Checks

**Files:**
- Create: `crates/runtime-core/src/mcp_client.rs`
- Modify: `crates/runtime-core/src/lib.rs`
- Test: `crates/runtime-core/tests/mcp_bridge.rs`
- Reference: `services/mcp-sidecar/src/protocol.ts`

**Step 1: Write the failing test**

```rust
#[test]
fn mcp_bridge_can_decode_health_response() {
    assert!(false, "needs rust bridge client");
}
```

**Step 2: Run test to verify it fails**

Run: `cargo test -p runtime-core mcp_bridge`
Expected: FAIL because the Rust bridge client does not exist

**Step 3: Write minimal implementation**

```rust
pub struct McpHealth {
    pub ok: bool,
}
```

Implement a supervised stdio client first; named pipes can stay out of scope until proven necessary.

**Step 4: Run test to verify it passes**

Run: `cargo test -p runtime-core mcp_bridge`
Expected: PASS

**Step 5: Commit**

```bash
git add crates/runtime-core
git commit -m "feat: add rust mcp sidecar bridge"
```

## Phase 6: Rust Session Runtime Migration

### Task 16: Port Session State, Logging, And Reply Orchestration

**Files:**
- Create: `crates/runtime-core/src/session.rs`
- Create: `crates/runtime-core/src/logging.rs`
- Create: `crates/runtime-core/src/reply.rs`
- Modify: `crates/runtime-core/src/lib.rs`
- Test: `crates/runtime-core/tests/reply_parity.rs`
- Reference: `src/local_ai_agent/runtime.py`
- Reference: `src/local_ai_agent/session_runner.py`
- Reference: `src/local_ai_agent/logging_utils.py`

**Step 1: Write the failing test**

```rust
#[test]
fn reply_fixture_round_trip_matches_python_shape() {
    assert!(false, "port session runtime");
}
```

**Step 2: Run test to verify it fails**

Run: `cargo test -p runtime-core reply_parity`
Expected: FAIL because the session runtime is not implemented

**Step 3: Write minimal implementation**

```rust
pub struct ReplyResult {
    pub content: String,
}
```

Port serialization and state shape before porting provider behavior.

**Step 4: Run test to verify it passes**

Run: `cargo test -p runtime-core reply_parity`
Expected: PASS

**Step 5: Commit**

```bash
git add crates/runtime-core
git commit -m "feat: port rust session runtime skeleton"
```

### Task 17: Port Provider Boundary Without Moving MCP Ownership Out Of Rust

**Files:**
- Create: `crates/runtime-core/src/providers.rs`
- Test: `crates/runtime-core/tests/providers.rs`
- Reference: `src/local_ai_agent/providers/base.py`
- Reference: `src/local_ai_agent/providers/fallback.py`

**Step 1: Write the failing test**

```rust
#[test]
fn provider_interface_supports_local_and_sidecar_backends() {
    assert!(false, "needs provider boundary");
}
```

**Step 2: Run test to verify it fails**

Run: `cargo test -p runtime-core providers`
Expected: FAIL because the provider abstraction does not exist in Rust

**Step 3: Write minimal implementation**

```rust
pub trait Provider {
    fn name(&self) -> &'static str;
}
```

Keep Rust in control of orchestration even when a provider or tool path delegates through the sidecar.

**Step 4: Run test to verify it passes**

Run: `cargo test -p runtime-core providers`
Expected: PASS

**Step 5: Commit**

```bash
git add crates/runtime-core
git commit -m "feat: add rust provider boundary"
```

## Phase 7: Optional Hub UI Module With React

### Task 18: Scaffold The Optional Hub Tauri UI Module With React + Vite + TanStack Router + TanStack Query

**Files:**
- Create: `apps/tauri-app/package.json`
- Create: `apps/tauri-app/vite.config.ts`
- Create: `apps/tauri-app/tsconfig.json`
- Create: `apps/tauri-app/src/main.tsx`
- Create: `apps/tauri-app/src/routes/__root.tsx`
- Create: `apps/tauri-app/src/routes/index.tsx`
- Create: `apps/tauri-app/src/router.tsx`
- Create: `apps/tauri-app/src/lib/queryClient.ts`
- Create: `apps/tauri-app/src/lib/state.ts`
- Create: `apps/tauri-app/src-tauri/Cargo.toml`
- Create: `apps/tauri-app/src-tauri/src/main.rs`
- Create: `apps/tauri-app/vitest.config.ts`
- Create: `apps/tauri-app/src/App.test.tsx`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";

describe("app shell", () => {
  it("renders the optional desktop shell", () => {
    expect(false).toBe(true);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix apps/tauri-app test`
Expected: FAIL because the optional Tauri UI module does not exist

**Step 3: Write minimal implementation**

```tsx
export function App() {
  return <main>CopilotTrae</main>;
}
```

Scaffold with React + Vite, not Next.js or another web-first meta-framework. Establish Router and Query providers immediately because this optional UI module is expected to grow into a multi-surface desktop experience for users who choose to install it from the Hub.

**Step 4: Run test to verify it passes**

Run: `npm --prefix apps/tauri-app test`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/tauri-app
git commit -m "chore: scaffold optional tauri ui module with react"
```

### Task 19: Add Hub Install Surface, Tauri Commands, Router Structure, And Query Wrappers

**Files:**
- Modify: `src/local_ai_agent/modules/manifest.py`
- Modify: `src/local_ai_agent/modules/registry.py`
- Modify: `src/local_ai_agent/modules/snapshot_builder.py`
- Modify: `apps/tauri-app/src-tauri/src/main.rs`
- Create: `apps/tauri-app/src/lib/api.ts`
- Create: `apps/tauri-app/src/lib/events.ts`
- Create: `apps/tauri-app/src/routes/chat.tsx`
- Create: `apps/tauri-app/src/routes/sessions.tsx`
- Create: `apps/tauri-app/src/routes/tools.tsx`
- Create: `apps/tauri-app/src/routes/logs.tsx`
- Create: `apps/tauri-app/src/routes/terminal.tsx`
- Test: `apps/tauri-app/src/lib/api.test.tsx`
- Test: `crates/runtime-core/tests/tauri_commands.rs`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";

describe("desktop api", () => {
  it("invokes rust command wrappers", () => {
    expect(false).toBe(true);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix apps/tauri-app test`
Expected: FAIL because no frontend API wrapper exists

**Step 3: Write minimal implementation**

```ts
export async function listTools() {
  return [];
}
```

Expose thin wrappers such as `listTools`, `sendChatMessage`, `previewTerminalInput`, `executeTerminalInput`, and `mcpStatus`, then bind them into `TanStack Query` hooks and `TanStack Router` routes without moving business logic into React.

Register the UI as an optional Hub module so the runtime can discover whether the desktop surface is installed without making it part of the default path.

**Step 4: Run test to verify it passes**

Run: `npm --prefix apps/tauri-app test`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/tauri-app
git commit -m "feat: register optional ui module and react route structure"
```

### Task 20: Add React Screens For Chat, Sessions, Tools, Logs, Terminal Preview, And MCP Health

**Files:**
- Create: `apps/tauri-app/src/components/ChatPane.tsx`
- Create: `apps/tauri-app/src/components/SessionPane.tsx`
- Create: `apps/tauri-app/src/components/ToolList.tsx`
- Create: `apps/tauri-app/src/components/LogPane.tsx`
- Create: `apps/tauri-app/src/components/TerminalPreview.tsx`
- Create: `apps/tauri-app/src/components/McpHealth.tsx`
- Create: `apps/tauri-app/src/components/ToastViewport.tsx`
- Modify: `apps/tauri-app/src/routes/__root.tsx`
- Test: `apps/tauri-app/src/components/*.test.tsx`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";

describe("terminal preview", () => {
  it("renders preview state", () => {
    expect(false).toBe(true);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix apps/tauri-app test`
Expected: FAIL because the UI components do not exist

**Step 3: Write minimal implementation**

```tsx
export function TerminalPreview({ command }: { command: string }) {
  return <section>{command}</section>;
}
```

Build the first React screens around the requested desktop surfaces: chat, sessions, tools, logs, and terminal previews. Add `Sileo` toast notifications for command outcomes and sidecar/runtime status changes. Keep the module self-contained so the system still operates fully when this UI is not installed.

**Step 4: Run test to verify it passes**

Run: `npm --prefix apps/tauri-app test`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/tauri-app
git commit -m "feat: add react desktop surfaces and toast notifications"
```

### Task 21: Add React UI Diagnostics, Audit Workflow, And Future Integration Notes

**Files:**
- Modify: `apps/tauri-app/package.json`
- Create: `apps/tauri-app/.react-doctor.json`
- Create: `docs/architecture/frontend-tooling-notes.md`
- Create: `docs/architecture/react-email-future-integration.md`
- Test: `apps/tauri-app/src/App.test.tsx`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";

describe("frontend tooling notes", () => {
  it("documents development and audit tools", () => {
    expect(false).toBe(true);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix apps/tauri-app test`
Expected: FAIL because the optional React UI tooling workflow and docs do not exist

**Step 3: Write minimal implementation**

```json
{
  "doctor": true
}
```

Document and wire the following for the optional UI module:

- `React Doctor` for development diagnostics,
- `Unlighthouse` for post-Phase-7 UI audits,
- `Fontpair` as a typography reference,
- Google `Stitch` as a personal design helper outside the dependency graph,
- `React Email` as a future integration path for email logging/auth workflows,
- `Caveman` as a concise execution convention for repetitive technical tasks.

**Step 4: Run test to verify it passes**

Run: `npm --prefix apps/tauri-app test`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/tauri-app/package.json apps/tauri-app/.react-doctor.json docs/architecture/frontend-tooling-notes.md docs/architecture/react-email-future-integration.md
git commit -m "docs: add react tooling and future integration notes"
```

### Task 22: Optional: Terminal Setup Installer

**Files:**
- Create: `install.ps1`
- Modify: `README.md`
- Test: `tests/test_install_script.py`

**Step 1: Write the failing test**

```python
from pathlib import Path


def test_install_script_exists_and_supports_terminal_prompt():
    script = Path("install.ps1")
    assert script.exists(), "install.ps1 must exist at repo root"

    content = script.read_text(encoding="utf-8")
    assert "Quieres instalar la terminal recomendada? (y/n)" in content
    assert "ajeetdsouza.zoxide" in content
    assert "eza-community.eza" in content
    assert "Set-PSReadLineOption -PredictionSource HistoryAndPlugin" in content
    assert "Set-PSReadLineOption -PredictionViewStyle ListView" in content
    assert "oh-my-posh" in content.lower() or "oh my posh" in content.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_install_script.py -v`
Expected: FAIL because the installer does not exist

**Step 3: Write minimal implementation**

```powershell
$installTerminal = Read-Host "Quieres instalar la terminal recomendada? (y/n)"
```

Create a root-level `install.ps1` that supports one-line execution from GitHub:

```powershell
irm 'https://raw.githubusercontent.com/maxiusofmaximus/CopilotTrae/main/install.ps1' | iex
```

The installer must:

- Run on Windows with `PowerShell 7+`
- Ask the user `Quieres instalar la terminal recomendada? (y/n)`
- If the answer is `y`, install `zoxide` and `eza` only when missing, enable predictive `PSReadLine`, and apply the complete profile with `Oh My Posh` plus the middleware
- If the answer is `n`, install and configure only the middleware path without terminal enhancements
- Be idempotent: detect existing installs and avoid reinstalling anything already present
- Update `$PROFILE` safely without duplicating blocks on repeated runs

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_install_script.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add install.ps1 README.md tests/test_install_script.py
git commit -m "feat: add optional terminal setup installer"
```

## Phase 8: Core Rust Cutover And Python Retirement

### Task 23: Add Parallel-Run Validation Between Python And Rust

**Files:**
- Create: `scripts/compare_python_rust_outputs.py`
- Create: `tests/contracts/parity/`
- Test: `tests/test_migration_parity.py`

**Step 1: Write the failing test**

```python
def test_python_and_rust_route_outputs_match_for_golden_cases():
    assert False, "needs parity runner"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_migration_parity.py -v`
Expected: FAIL because parity comparison tooling does not exist

**Step 3: Write minimal implementation**

```python
def compare_payloads(left: dict, right: dict) -> list[str]:
    return [] if left == right else ["payload mismatch"]
```

Compare Python and Rust outputs for all frozen fixtures before any default CLI and middleware cutover. The optional Tauri UI module does not block this transition.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_migration_parity.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/compare_python_rust_outputs.py tests/contracts/parity tests/test_migration_parity.py
git commit -m "test: add python rust parity runner"
```

### Task 24: Flip Default Entry Points Only After Parity Sign-Off

**Files:**
- Modify: `README.md`
- Modify: `scripts/powershell/middleware.ps1`
- Modify: `crates/cli-app/src/commands.rs`
- Test: `tests/test_powershell_middleware.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
def test_default_cli_backend_can_switch_to_rust_after_signoff():
    assert False, "guard default cutover behind explicit readiness"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py tests/test_powershell_middleware.py -v`
Expected: FAIL because default cutover gating is not implemented

**Step 3: Write minimal implementation**

```python
DEFAULT_BACKEND = "python"
```

Keep the default conservative until parity evidence and operator sign-off exist, then change the CLI and middleware defaults in one isolated commit. The optional Tauri UI module can ship later without blocking core cutover.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py tests/test_powershell_middleware.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add README.md scripts/powershell/middleware.ps1 crates/cli-app/src/commands.rs tests/test_cli.py tests/test_powershell_middleware.py
git commit -m "feat: gate rust default cutover behind readiness flag"
```

## Validation Checklist

- Python tests stay green while their subsystem remains active.
- Rust contract types deserialize Python golden fixtures without lossy field drops.
- Rust `route` matches fixture parity before any execution path switches.
- Rust `exec --json` matches middleware expectations before interactive execution cutover.
- The MCP sidecar runs headless and passes isolated Vitest coverage.
- FastMCP reduces sidecar adapter boilerplate without obscuring transport contracts.
- The system remains fully functional without Tauri installed.
- The Hub controls discovery and installation of the optional desktop UI module.
- Tauri frontend talks only to Rust commands/events.
- The React app has route/query structure appropriate for chat, sessions, tools, logs, and terminal preview surfaces.
- Development diagnostics and audit workflows exist for React (`React Doctor`) and UI quality (`Unlighthouse`).
- The desktop app remains optional; CLI and middleware paths continue to work headless before, during, and after core Rust cutover.

## Plan Notes

- The product identity remains minimal terminal-first: `??` in PowerShell, command correction, and deterministic routing through CLI and middleware.
- The frontend baseline is intentionally structured only for the optional UI module: React, TanStack Router, TanStack Query, Vite, thin Tauri command wrappers.
- Keep React complexity justified by product surface area; do not move domain logic out of Rust.
- Use `Sileo`, `React Doctor`, `Unlighthouse`, `Fontpair`, Google `Stitch`, and `React Email` only in the roles defined above.
- Prefer fixture parity and trace comparison over speculative rewrites.
- Keep commits small and reversible so the migration can pause safely after any phase.

Plan complete and saved to `docs/plans/2026-04-18-rust-ts-tauri-migration-implementation.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
