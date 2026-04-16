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
