# Migration To Rust + TypeScript + Tauri

## Status

This document defines the target architecture and migration strategy for moving the current Python implementation to a split stack based on Rust, TypeScript, and Tauri.

Fixed decisions:

- Rust owns the deterministic local runtime and desktop-native boundary.
- TypeScript owns MCP connectivity and web-facing integrations.
- Tauri is the desktop shell and UI bridge, not the business logic center.
- The MCP client runs as a separate TypeScript sidecar process.
- The current Python system remains active until each replacement passes equivalent contract and integration coverage.

## Goals

- Preserve the current deterministic terminal middleware behavior while migrating the implementation stack.
- Add a desktop application without collapsing routing, execution, UI, and external integrations into one layer.
- Introduce a first-class MCP integration surface for Context7, Playwright, Brave Search, and future MCP servers.
- Keep the system operable without the desktop UI so terminal and automation flows can continue to run headless.
- Preserve or improve the current test coverage instead of restarting from zero during the rewrite.

## Non-Goals

- Rewriting everything in one cutover.
- Embedding MCP orchestration directly into the Tauri frontend.
- Letting the desktop layer execute tools or business logic directly.
- Removing Python before the replacement stack has parity on the validated behaviors.

## Current System Baseline

Today the repository is a Python CLI-first agent with these active responsibilities:

- Session orchestration and reply/chat flows.
- Deterministic terminal routing and host execution mediation.
- Tool discovery and registry snapshot construction.
- Provider abstraction and LLM invocation.
- Multimodal preprocessing and OCR entry points.
- JSONL logging and router event persistence.
- A PowerShell middleware wrapper that depends on `local-ai-agent exec --json` and `local-ai-agent exec`.

The migration must preserve the contracts already visible in the current CLI and middleware flow, especially:

- `route` returns machine-readable JSON only.
- `exec --json` returns a route envelope only.
- execution remains outside the pure routing layer.
- terminal correction flows remain deterministic and explainable.

## Recommended Target Architecture

The target system is a three-layer runtime with narrow boundaries:

- Rust core runtime for deterministic local logic, policy enforcement, terminal mediation, provider abstraction, local state, and durable contracts.
- TypeScript sidecar for MCP transport, remote/web-oriented integrations, browser automation clients, and adapter logic for third-party MCP servers.
- Tauri desktop shell for UI, desktop lifecycle, permissions, windowing, tray, notifications, and safe invocation of Rust commands.

At a high level:

```text
PowerShell / CLI / Tauri UI
        |
        v
   Rust Core Runtime
        |
        +---- local OS boundary (tool execution, files, policies, logging)
        |
        +---- JSON-RPC over stdio/socket ----> TypeScript MCP Sidecar
                                                |
                                                +---- Context7 MCP server
                                                +---- Playwright MCP server
                                                +---- Brave Search MCP server
                                                +---- future MCP servers
```

This split keeps deterministic local behavior close to the OS in Rust, while isolating fast-changing integration code in TypeScript where MCP tooling is strongest.

## What Lives In Rust

Rust should own the parts of the current system that benefit from strong typing, deterministic execution, local trust boundaries, and long-lived desktop/runtime stability.

### Rust Responsibilities

- CLI entrypoints that replace `local-ai-agent reply`, `chat`, `route`, `exec`, and `terminal`.
- Deterministic router and route envelope generation.
- Terminal host logic, confirmation policies, trust policy checks, and execution guardrails.
- Tool registry, module registry, and snapshot building.
- Core agent session orchestration and memory lifecycle.
- Provider abstraction and direct model calls where a provider does not require MCP.
- Local persistence for logs, session memory, snapshots, config, and audit trails.
- Multimodal routing policy and OCR orchestration boundaries.
- Tauri command handlers and desktop-safe service surface.

### Why These Parts Belong In Rust

- They are the safety-critical boundary between user intent and execution.
- They define stable contracts already validated by the current Python tests.
- They benefit from predictable concurrency, low overhead, and tighter control over subprocesses and filesystem access.
- They should remain available both with and without the desktop UI.
- They are the least desirable place for dependency churn from browser and web tooling.

### Likely Python-To-Rust Mappings

- `src/local_ai_agent/router/*` -> Rust routing crate/module.
- `src/local_ai_agent/terminal/*` -> Rust execution/terminal module.
- `src/local_ai_agent/runtime.py` and `session_runner.py` -> Rust application runtime layer.
- `src/local_ai_agent/tools/*` and `modules/*` -> Rust registry/snapshot services.
- `src/local_ai_agent/logging_utils.py`, memory, config, and core contracts -> Rust support crates/modules.

### Rust Should Not Own

- Browser-centric integration code for MCP servers.
- Fast-moving glue code for third-party MCP transports.
- Frontend rendering logic.

## What Lives In TypeScript

TypeScript should own the integration layer where the ecosystem advantage is highest: MCP clients, web-facing tools, browser automation integrations, and adapters that benefit from JavaScript-first libraries.

### TypeScript Responsibilities

- The standalone MCP sidecar process.
- MCP client/session management.
- Connectors to Context7, Playwright, Brave Search, and future MCP servers.
- Tool schema normalization from MCP into a contract the Rust core can consume.
- Streaming adapters for MCP responses, tool calls, progress events, and structured errors.
- Optional provider adapters that are better served by JS ecosystems, if needed later.
- Integration-focused diagnostics and health checks for MCP availability.

### Why These Parts Belong In TypeScript

- MCP tooling, examples, and libraries are currently strongest in the Node/TypeScript ecosystem.
- Browser automation stacks such as Playwright are first-class in TypeScript.
- Search/documentation connectors often ship earlier and with better support in JS runtimes.
- Keeping this as a sidecar lets it run headless, independent of Tauri, and easy to test in isolation.

### MCP Sidecar Scope

The sidecar is not the source of truth for routing policy, memory, or execution decisions. It is an integration broker that:

- establishes MCP connections,
- exposes available tools/resources/prompts,
- executes MCP requests on behalf of Rust,
- returns structured results and errors,
- streams progress when relevant.

### TypeScript Should Not Own

- Terminal execution.
- Desktop permissions.
- Persistent local policy enforcement.
- The canonical router contract.
- The final decision to run a command on the host system.

## What Tauri Does

Tauri is the desktop delivery shell. It packages the Rust core and provides a native desktop app without becoming the orchestration layer.

### Tauri Responsibilities

- App lifecycle, windows, tray, notifications, and desktop packaging.
- Invoking approved Rust commands from the frontend.
- Rendering the UI for chat, logs, tools, sessions, and operator controls.
- Managing secure desktop capabilities such as file pickers, clipboard prompts, and OS-level integrations through Tauri permissions.
- Shipping the Rust runtime and coordinating startup of the TypeScript MCP sidecar when the UI is used.

### Tauri Does Not Touch

- Deterministic routing internals.
- Direct MCP protocol logic.
- Direct subprocess execution policy beyond delegating to Rust.
- Business rules for trust policy, correction policy, or tool resolution.

### Why Tauri Is The Right Role

- It gives a native desktop surface while preserving a Rust backend.
- It allows the UI to stay thin and replaceable.
- It keeps the headless path viable: the Rust CLI and the TypeScript sidecar can still run without opening the desktop app.

## Layer Boundaries And Communication

The architecture should prefer simple, explicit, inspectable boundaries over in-process coupling.

### Boundary 1: Frontend <-> Rust

Frontend to Rust communication should use Tauri commands/events only.

- Format: JSON payloads with versioned request/response types.
- Invocation pattern: request/response for commands, event streams for progress and logs.
- Ownership: Rust defines the canonical schema because it owns business behavior.

Good candidates:

- `send_chat_message`
- `preview_terminal_input`
- `execute_terminal_input`
- `list_tools`
- `get_session_state`
- `tail_logs`
- `mcp_status`

The frontend must never talk directly to the MCP sidecar.

### Boundary 2: Rust <-> TypeScript Sidecar

Rust and the MCP sidecar should communicate over a local RPC boundary.

Recommended default:

- Protocol: JSON-RPC 2.0
- Transport: stdio first, optional local domain socket or named pipe later
- Encoding: UTF-8 JSON
- Framing: standard JSON-RPC message framing over stdio or line-delimited framed transport if a custom bridge is needed

Reasoning:

- JSON-RPC maps naturally to MCP-style request/response and notifications.
- stdio works well for sidecars, local supervision, and test harnesses.
- It is cross-platform and easy to capture in integration tests.
- It allows the sidecar to run without Tauri and without network exposure.

Suggested Rust-to-sidecar operations:

- `mcp.initialize`
- `mcp.listServers`
- `mcp.listTools`
- `mcp.callTool`
- `mcp.readResource`
- `mcp.health`
- `mcp.shutdown`

### Boundary 3: Shell Middleware <-> Rust CLI

The current PowerShell middleware should continue to talk to a CLI surface during migration and after migration.

- Format: stdout JSON for machine-readable mode, human-readable text for interactive mode
- Contract preserved:
  - `route` returns JSON only
  - `exec --json` returns JSON only
  - `exec` handles confirmation/execution UX

This compatibility layer is what lets Python remain untouched until a Rust replacement has parity.

## Data Contracts

Migration safety depends on preserving a few canonical payloads even if internal implementations change.

### Canonical Contracts To Freeze Early

- `TerminalRequest`
- `RouteEnvelope`
- `RouterErrorEnvelope`
- session request/response payloads for reply/chat
- tool execution preview/result payloads
- log event schema
- MCP bridge request/response/error schema

### Serialization Rules

- All cross-process contracts use UTF-8 JSON.
- All externally visible contracts are versioned.
- Envelope fields are additive when possible.
- Errors are structured and machine-readable.
- Logs remain append-only JSONL unless a later design explicitly changes storage.

## Migration Strategy

The migration should be incremental, contract-first, and reversible at each layer.

### Phase 0: Freeze And Mirror Contracts

- Freeze the Python-visible JSON contracts now.
- Export representative golden fixtures from the current Python runtime.
- Capture real middleware traces and representative CLI transcripts.
- Define parity criteria for `route`, `exec --json`, `exec`, `reply`, and `chat`.

Python remains the production path.

### Phase 1: Build Rust Contract Harness

- Create a Rust workspace with crates/modules for contracts, router, terminal, runtime, and CLI.
- Reproduce contract serialization first, before full behavior.
- Stand up a Rust CLI that can emit the same envelope shapes as Python for fixture-based tests.

Python remains the production path.

### Phase 2: Migrate Deterministic Router To Rust

- Reimplement the router, registry snapshot builder, and route serialization in Rust.
- Run the current router-focused tests and golden traces against Rust equivalents.
- Keep Python `exec` and session flows active until route parity is proven.

At this point, Rust can replace `route` first because it has the smallest surface and strongest contract.

### Phase 3: Migrate Terminal Host And CLI Execution To Rust

- Reimplement host execution mediation, dry-run, confirmation, trust policy, and empty-command blocking.
- Validate against the existing terminal integration scenarios and real console scenarios.
- Switch PowerShell middleware from Python CLI to Rust CLI only after the replacement passes parity tests.

Python session/chat flows still remain active.

### Phase 4: Introduce TypeScript MCP Sidecar

- Build the TS sidecar as a separately runnable process.
- Implement MCP connectivity to Context7, Playwright, Brave Search, and future servers.
- Add a Rust bridge client that talks JSON-RPC over stdio to the sidecar.
- Keep MCP-derived capabilities behind a feature boundary until reliability and schemas are stable.

Python remains untouched because this introduces new capability, not a required cutover.

### Phase 5: Migrate Session Runtime To Rust

- Move chat/reply orchestration, memory, logging, config, and provider abstraction into Rust.
- If some providers are easier to reach through MCP or TS, access them through the sidecar boundary without moving ownership of session orchestration out of Rust.
- Validate chat/reply parity using fixture-based and end-to-end tests.

Only after this phase should the Python session runtime be considered replaceable.

### Phase 6: Add Tauri Desktop Shell

- Wrap the Rust core with Tauri command handlers.
- Add the TypeScript frontend UI.
- Start and supervise the MCP sidecar from the desktop app when needed.
- Preserve a headless CLI path independent of the desktop shell.

Tauri arrives after the runtime is stable, not before.

### Phase 7: Controlled Cutover And Python Retirement

- Run both implementations in parallel during a validation window.
- Compare output envelopes, logs, and selected end-to-end traces.
- Switch default entrypoints to Rust/Tauri only after parity and operational readiness are confirmed.
- Retire Python modules gradually once they are no longer the active path and the replacement is proven.

## What Happens To The Current 100 Tests

The current tests are an asset, not legacy noise. They should become the migration safety net.

### Preservation Strategy

- Keep the Python suite green during the transition.
- Classify the tests by contract domain instead of by language:
  - router contracts,
  - terminal behavior,
  - middleware integration,
  - runtime/session behavior,
  - multimodal/OCR behavior,
  - logging and safety behavior.
- Convert the most valuable Python tests into language-agnostic fixtures and trace-based contract tests.
- Reimplement equivalent tests in Rust and TypeScript only when the target layer is ready.

### Recommended Test Layers After Migration

- Rust unit tests for router, terminal host, runtime, config, and serialization.
- Rust integration tests for CLI behavior and sidecar bridge behavior.
- TypeScript unit/integration tests for MCP sidecar adapters and server compatibility.
- Tauri integration tests for command bindings and frontend/backend wiring.
- End-to-end contract tests that replay the current golden fixtures across both Python and Rust during transition.

### Practical Handling Of The Existing 100 Tests

- Keep them running in CI while Python is still the active implementation.
- Tag the most critical tests as parity blockers for migration phases.
- For each migrated subsystem, create a replacement test matrix before removing the Python implementation.
- Do not delete a Python test until:
  - the subsystem is no longer active,
  - an equivalent Rust/TS/Tauri test exists,
  - parity evidence is recorded.

## Recommended Repository Shape

One workable target layout is:

```text
apps/
  tauri-app/                 # Tauri app and TS frontend
crates/
  core-contracts/            # shared Rust contracts
  router-core/               # deterministic router
  terminal-core/             # host execution and trust policy
  runtime-core/              # chat/reply orchestration, memory, logs
  cli-app/                   # Rust CLI replacement for local-ai-agent
services/
  mcp-sidecar/               # TypeScript MCP process
tests/
  contracts/                 # golden fixtures, transcripts, parity traces
docs/
  architecture/
```

The exact folder names can change, but the separation should remain.

## Risks And Mitigations

### Risk: Rewriting Too Many Layers At Once

Mitigation:

- Migrate in contract order: router, then terminal, then session runtime, then desktop shell.

### Risk: Tauri Becomes A God Layer

Mitigation:

- Keep all meaningful commands in Rust and let the frontend remain thin.

### Risk: MCP Sidecar Leaks Into Core Policy

Mitigation:

- Rust remains the authority for routing, trust policy, and execution decisions.

### Risk: Coverage Collapses During Rewrite

Mitigation:

- Preserve Python tests, add golden fixtures, and require parity evidence before cutover.

### Risk: Python Gets Modified Mid-Migration

Mitigation:

- Keep Python stable and patch only production issues until a replacement is validated.

## Recommended Final Decisions

- Rust is the system of record for deterministic local runtime behavior.
- TypeScript is the integration plane for MCP and browser/search/documentation ecosystems.
- Tauri is the desktop shell, not the orchestration core.
- Rust and TypeScript communicate over local JSON-RPC, starting with stdio.
- Migration proceeds in contract-first slices with Python retained until each replacement is proven.
- The existing 100 tests become the baseline parity harness for the rewrite.

## Open Items For The Later Implementation Plan

These are intentionally deferred until the implementation-planning phase:

- exact Rust crate boundaries,
- exact frontend stack inside the Tauri app,
- whether OCR remains local in Rust or moves behind an optional service boundary,
- process supervision details for the sidecar on Windows/macOS/Linux,
- release packaging and updater strategy,
- CI matrix for running Python and Rust parity jobs side by side.
