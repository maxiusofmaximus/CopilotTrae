# Local AI Agent

Provider-agnostic local CLI AI agent for structured chat workflows.

## What It Does

This project ships a real CLI-first agent with strict boundaries between:

- input adapters
- normalization and orchestration
- provider-agnostic LLM calls
- short-term memory
- output adapters
- optional future automation hooks

The v1 workflow is deterministic:

`input -> normalize -> LLM -> post-process -> output`

UI automation is intentionally not implemented yet, but the automation interface is already present so it can be added later without refactoring the core agent.

## Features

- Provider-agnostic `LLMClient` abstraction
- OpenAI-compatible message schema and payloads
- Cerebras adapter implemented first
- Short-term conversation memory with bounded trimming
- JSONL interaction logging
- CLI reply mode and interactive chat mode
- Confirmation before clipboard side effects by default
- Pluggable input, output, and automation interfaces

## Install

```bash
python -m pip install -e .[dev]
```

## Configure

Set the provider credentials through environment variables.

### PowerShell

```powershell
$env:CEREBRAS_API_KEY="your-cerebras-key"
$env:LOCAL_AI_AGENT_PROVIDER="cerebras"
$env:LOCAL_AI_AGENT_MODEL="gpt-oss-120b"
```

The Cerebras adapter uses the OpenAI-compatible endpoint at `https://api.cerebras.ai/v1` according to the Cerebras compatibility docs: [OpenAI Compatibility](https://inference-docs.cerebras.ai/resources/openai).

Optional settings:

- `LOCAL_AI_AGENT_SYSTEM_PROMPT`
- `LOCAL_AI_AGENT_MAX_MEMORY_MESSAGES`
- `LOCAL_AI_AGENT_MAX_TOKENS`
- `LOCAL_AI_AGENT_TIMEOUT_SECONDS`
- `LOCAL_AI_AGENT_MAX_RETRIES`
- `LOCAL_AI_AGENT_LOGS_DIR`
- `LOCAL_AI_AGENT_CONFIRM_BEFORE_COPY`

## Usage

### PowerShell Terminal Middleware

If you want to see the terminal middleware working end-to-end, start here. This is the real PowerShell flow for a mistyped command: the wrapper detects the failed command, asks the deterministic router for a machine-readable decision through `local-ai-agent exec --json`, and then executes the human-facing correction flow through `local-ai-agent exec`.

```powershell
"y" | pwsh -NoProfile -File .\scripts\powershell\middleware.ps1 github.cli --version
```

Expected output:

```text
Router route: command_fix
Command not found.

Suggested command:
gh --version

Execute suggested command? (y/n): Executed suggested command: gh --version
gh version 2.89.0 (2026-03-26)
https://github.com/cli/cli/releases/tag/v2.89.0
```

What this demonstrates:

- `middleware.ps1` only falls back when the original command is not found or exits non-zero
- the middleware gets the route envelope through `local-ai-agent exec --json`, so it uses the active snapshot already bound by the runtime
- the human-facing decision and confirmation happen through `local-ai-agent exec`
- a successful command passthrough remains transparent when no fallback is needed
- router events are persisted to `logs/router/<session-id>.jsonl` after each real resolution

## Operation

- Runbook: [docs/runbooks/production-readiness.md](docs/runbooks/production-readiness.md)
- Smoke script: [scripts/smoke/production_readiness.ps1](scripts/smoke/production_readiness.ps1)

Quick checks:

```powershell
pwsh -NoProfile -File .\scripts\smoke\production_readiness.ps1
```

```powershell
$env:LOCAL_AI_AGENT_MIDDLEWARE_DISABLED = "1"
pwsh -NoProfile -File .\scripts\powershell\middleware.ps1 gh --version
```

### One-Shot Reply

```bash
local-ai-agent reply --text "Summarize this support request and draft a reply."
```

### Pipe Input Through Stdin

```bash
Get-Content .\message.txt | local-ai-agent reply
```

### Read Input From A File

```bash
local-ai-agent reply --input-file .\message.txt
```

### Copy Response To Clipboard With Confirmation

```bash
local-ai-agent reply --text "Draft a concise answer." --copy
```

### Show Visible Memory State

```bash
local-ai-agent reply --text "What did we decide earlier?" --show-memory
```

### Interactive Session

```bash
local-ai-agent chat --show-memory
```

Exit the interactive session with `/exit` or `/quit`.

### Route Middleware Mode

The `route` command is the deterministic middleware surface for terminal routing. It does not execute commands, install tools, or mutate registries. It only builds a `TerminalRequest`, calls a bound router runtime, and emits the resulting envelope as JSON to `stdout`.

Example invocation shape:

```bash
local-ai-agent route --text "gh --version" --shell powershell --cwd C:\repo --snapshot-version snap-1
```

Output contract:

- `stdout` contains JSON only
- no debug prints
- no human-oriented prose
- no command execution side effects

Current integration note:

- `build_runtime()` now injects `router_runtime` into `AppRuntime` for in-process CLI and host flows
- direct `route` calls still require an explicit `--snapshot-version` and remain useful for contract testing
- the PowerShell middleware no longer invents a placeholder snapshot version; it asks `exec --json` for the active routed envelope instead

## Deterministic Middleware Boundaries

Purpose:

- classify terminal input into a JSON-only routing envelope
- preserve deterministic resolution against a bound snapshot
- hand off execution decisions to the host terminal layer

Non-goals:

- executing subprocesses from the router or CLI `route` path
- installing packages or changing registries from the router runtime
- importing execution logic from external reference repositories

Reference-repo policy:

- repositories such as `Claudia`, `DEV-OS`, `AsistenteW11`, and `AsistHub` are references for behavior and constraints only
- this repository does not embed or delegate execution to those projects

## Logs

Every interaction is written to a session JSONL file under `logs/` by default.

Each record includes:

- timestamp
- provider and model
- normalized request input
- full request message list
- response content
- finish reason
- token usage when the provider returns it

Router resolutions also write JSONL events under `logs/router/<session-id>.jsonl`.

Each router event record includes:

- `event_name`
- request and session identifiers
- the bound `snapshot_version`
- route or error details emitted during resolution

## Architecture Notes

- `src/local_ai_agent/models.py`: OpenAI-style request and response models
- `src/local_ai_agent/providers/base.py`: provider interface and provider errors
- `src/local_ai_agent/providers/cerebras.py`: concrete Cerebras adapter
- `src/local_ai_agent/memory.py`: bounded short-term memory
- `src/local_ai_agent/agent.py`: deterministic pipeline controller
- `src/local_ai_agent/input_adapters.py`: manual, stdin, and file inputs
- `src/local_ai_agent/output_adapters.py`: console and clipboard outputs
- `src/local_ai_agent/automation.py`: placeholder automation interface for future UI injection
- `src/local_ai_agent/cli.py`: CLI control surface

Current terminal wiring:

- `build_runtime()` creates the session runner and injects `router_runtime` into `AppRuntime`
- `router_runtime` resolves against a cached snapshot provider instead of an embedded snapshot value
- `middleware.ps1` uses `exec --json` for machine-readable routing and `exec` for the interactive correction or execution step
- `JsonlRouterEventSink` persists router events for every real resolution

## Safety Defaults

- Clipboard side effects require confirmation by default
- Full UI injection is not enabled in v1
- The runtime can be interrupted safely with `Ctrl+C`
- Interactions are logged for traceability
- Memory is bounded to avoid uncontrolled context growth

## Next Steps

- Add a real clipboard listener input adapter
- Add provider fallback routing above the `LLMClient` layer
- Add persistent conversation sessions
- Add guarded automation adapters for Playwright, AutoHotkey, or `pyautogui`

## Future Migration

- `Python` is the active implementation stack for the current middleware phases
- `Rust + TypeScript + Tauri` is the agreed definitive stack after Python behavior, contracts, and middleware traces are fully validated
- that migration is a later closed phase, not an open design question during the current plan
