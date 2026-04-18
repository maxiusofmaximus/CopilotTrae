# Migration To Rust + TypeScript + Tauri

## Status

This document defines the target architecture and migration strategy for moving the current Python implementation to a split stack based on Rust and TypeScript, with Tauri treated as an optional Hub-installed UI module.

## Fixed Decisions

- Rust owns deterministic routing, terminal mediation, runtime state, and the primary CLI and middleware product surface.
- TypeScript owns MCP connectivity and web-facing integrations through a separate sidecar process.
- Tauri is not the default product surface; it is an optional Hub module that provides a desktop UI for users who choose to install it.
- The current Python system remains active until each replacement passes equivalent contract and integration coverage.

## Goals

- Preserve the current deterministic terminal middleware behavior while migrating the implementation stack.
- Keep the system fully operable without the desktop UI so terminal and automation flows continue to run headless.
- Introduce contract fixtures that freeze current Python behavior before core migration work begins.
- Preserve or improve current test coverage instead of restarting from zero during the rewrite.

## Current System Baseline

Today the repository is a Python CLI-first agent with these active responsibilities:

- Session orchestration and reply/chat flows.
- Deterministic terminal routing and host execution mediation.
- Tool discovery and registry snapshot construction.
- Provider abstraction and LLM invocation.
- Multimodal preprocessing and OCR entry points.
- A PowerShell middleware wrapper that depends on `local-ai-agent exec --json` and `local-ai-agent exec`.

The migration must preserve the contracts already visible in the current CLI and middleware flow, especially:

- `route` returns machine-readable JSON only.
- `exec --json` returns a route envelope only.
- Execution remains outside the pure routing layer.
- Terminal correction flows remain deterministic and explainable.

## Recommended Target Architecture

The target system is a terminal-first runtime with narrow boundaries:

- Rust core runtime for deterministic local logic, policy enforcement, terminal mediation, provider abstraction, local state, and durable contracts.
- TypeScript sidecar for MCP transport, remote/web-oriented integrations, browser automation clients, and adapter logic for third-party MCP servers.
- Optional Tauri Hub module for UI, desktop lifecycle, notifications, and safe invocation of Rust commands when users install that module.

At a high level:

```text
PowerShell / CLI / Middleware
        |
        v
   Rust Core Runtime
        |
        +---- local OS boundary (tool execution, files, policies, logging)
        |
        +---- JSON-RPC over stdio ----> TypeScript MCP Sidecar
        |
        +---- optional Hub-installed Tauri UI
```

## Contract Fixtures

Migration work starts by exporting golden fixtures from the active Python implementation.

- `tests/contracts/router/` stores routing envelopes and command-fix outputs.
- `tests/contracts/terminal/` stores execution mediation payloads.
- `tests/contracts/runtime/` stores session, reply, and chat payloads.

These fixtures are the parity baseline for later Rust and TypeScript implementations. They must remain machine-readable, versionable, and easy to diff in tests.
