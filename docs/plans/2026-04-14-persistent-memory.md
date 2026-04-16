# Persistent Memory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a file-backed persistent `MemoryStore` that survives process restarts and plugs into the existing architecture without changing `AgentController` behavior or adding orchestration logic to the CLI.

**Architecture:** Introduce a persistent `MemoryStore` implementation backed by JSONL, plus a small runtime composition module that selects the appropriate memory store from `Settings`. Move dependency construction out of `cli.py` so extensions plug in at a non-CLI seam, keeping session behavior in `AgentSessionRunner` and core behavior in `AgentController`.

**Tech Stack:** Python 3.12, `pydantic`, `argparse`, `pytest`, JSONL file storage

---

### Task 1: Prove The Composition Seam

**Files:**
- Test: `tests/test_cli.py`
- Create: `tests/test_runtime.py`

**Step 1:** Add a failing test showing CLI delegates runtime creation to a non-CLI composition function.
**Step 2:** Run the targeted test and verify it fails for the expected reason.
**Step 3:** Add the minimal runtime composition module and update wiring.
**Step 4:** Re-run the targeted test and verify it passes.

### Task 2: Add Persistent Memory Tests

**Files:**
- Test: `tests/test_memory.py`
- Test: `tests/test_runtime.py`

**Step 1:** Add failing tests for restart survival, context reconstruction, trimming, and settings-based memory selection.
**Step 2:** Run only those tests and verify they fail for the expected missing implementation.

### Task 3: Implement Persistent Memory

**Files:**
- Modify: `src/local_ai_agent/config.py`
- Modify: `src/local_ai_agent/memory.py`
- Create: `src/local_ai_agent/runtime.py`

**Step 1:** Add settings for persistent memory enablement and file path.
**Step 2:** Implement a JSONL-backed `PersistentConversationMemory` that loads prior messages, appends safely, and preserves trimming behavior.
**Step 3:** Add runtime selection logic that returns either in-memory or persistent memory via the `MemoryStore` contract.
**Step 4:** Re-run focused tests until green.

### Task 4: Verify Integration

**Files:**
- Test: `tests/`
- Diagnostics: touched source and test files

**Step 1:** Run `pytest -v`.
**Step 2:** Run diagnostics on touched files and fix any issues.
**Step 3:** Confirm `AgentController` and CLI boundaries remain intact.
