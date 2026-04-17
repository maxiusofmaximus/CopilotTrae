# Terminal Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden terminal middleware UX and shell fallback behavior so `exec`, `terminal`, and the PowerShell wrapper feel safe and usable in real terminal workflows.

**Architecture:** Keep the router JSON-only and preserve `TerminalHost` as the decision layer plus source of human-facing terminal copy. Extend `cli.py` only as a thin transport for flags and rendering, and harden `middleware.ps1` with explicit recursion protection and fallback detection based on real command failures.

**Tech Stack:** Python 3.12, stdlib `argparse`/`json`/`pathlib`, existing terminal host/executor abstractions, PowerShell, `pytest`

---

### Task 1: Harden terminal UX output

**Files:**
- Create: `tests/test_terminal_ux.py`
- Modify: `src/local_ai_agent/terminal/host.py`
- Modify: `src/local_ai_agent/cli.py`

**Step 1: Write the failing test**
- Add a test that runs `local-ai-agent exec github.cli --version` with declined confirmation and asserts readable spacing:
  - `Command not found.` on its own line
  - blank line before `Suggested command:`
  - suggested command rendered on its own line
  - prompt rendered as `Execute suggested command? (y/n):`

**Step 2: Run test to verify it fails**
- Run: `pytest tests/test_terminal_ux.py::test_exec_output_formats_command_fix_with_clear_spacing -q`
- Expected: FAIL because current output is compact and the prompt format does not match the hardened UX.

**Step 3: Write minimal implementation**
- Move human-facing copy for terminal decisions into `TerminalHost`.
- Add host-level formatting helpers for:
  - `suggest_correction`
  - `blocked`
  - `clarify`
  - `executed`
- Keep `cli.py` responsible only for transport, prompts, and writing already prepared lines.

**Step 4: Run test to verify it passes**
- Run: `pytest tests/test_terminal_ux.py::test_exec_output_formats_command_fix_with_clear_spacing -q`
- Expected: PASS

### Task 2: Add safe `exec` flags

**Files:**
- Modify: `tests/test_terminal_integration.py`
- Modify: `tests/test_terminal_ux.py`
- Modify: `src/local_ai_agent/cli.py`

**Step 1: Write the failing tests**
- Add tests for:
  - `--yes` executes suggested command without prompting
  - `--dry-run` never executes
  - `--json` writes only raw JSON to stdout
  - `--debug` writes route/debug details without polluting normal output

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/test_terminal_integration.py tests/test_terminal_ux.py -q`
- Expected: FAIL because flags do not exist yet.

**Step 3: Write minimal implementation**
- Add new `exec` flags and branch behavior in `cli.py`.
- Preserve correction confirmation default unless `--yes` is explicitly set.
- Make `--json` print only serialized envelope content.

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/test_terminal_integration.py tests/test_terminal_ux.py -q`
- Expected: PASS

### Task 3: Harden PowerShell fallback

**Files:**
- Create: `tests/test_powershell_middleware.py`
- Modify: `scripts/powershell/middleware.ps1`

**Step 1: Write the failing tests**
- Add tests that verify:
  - fallback activates only for command-not-found or non-zero exit from normal execution
  - recursion is prevented with an explicit guard variable or sentinel
  - wrapper delegates to `local-ai-agent exec` only after routing

**Step 2: Run tests to verify they fail**
- Run: `pytest tests/test_powershell_middleware.py -q`
- Expected: FAIL because recursion protection and failure detection are not implemented.

**Step 3: Write minimal implementation**
- Add a recursion guard environment variable.
- Execute the original command first.
- Inspect failure shape and only call router/exec when fallback criteria are met.

**Step 4: Run tests to verify they pass**
- Run: `pytest tests/test_powershell_middleware.py -q`
- Expected: PASS

### Task 4: Full verification

**Files:**
- Test: `tests/test_terminal_integration.py`
- Test: `tests/test_terminal_ux.py`
- Test: `tests/test_powershell_middleware.py`
- Test: existing full suite

**Step 1: Run focused tests**
- Run: `pytest tests/test_terminal_integration.py tests/test_terminal_ux.py tests/test_powershell_middleware.py tests/test_terminal_host.py tests/test_cli.py -q`
- Expected: PASS

**Step 2: Run full suite**
- Run: `pytest -q`
- Expected: PASS

## Plan Closure

Status: closed

Exit criteria satisfied:

- full suite green with `pytest -q`
- production smoke green with `pwsh -NoProfile -File .\scripts\smoke\production_readiness.ps1`
- pilot checklist documented in `docs/runbooks/production-readiness.md`
- `GO` / `NO-GO` gate documented with explicit `PASS` / `FAIL` criteria and closure template

Operational result:

- the production readiness path is complete and the Hub frontend can start from this baseline
