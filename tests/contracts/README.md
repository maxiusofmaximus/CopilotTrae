# Contract Fixtures

This directory stores migration fixtures exported from the active Python runtime.

## Source Of Truth

- Python remains the source of truth until the Rust and TypeScript replacements prove parity.
- Fixtures in this tree are generated from current machine-readable CLI and runtime contracts.
- Rust and TypeScript implementations must deserialize and match these payloads before cutover.

## Layout

- `router/`: deterministic routing envelopes and command-fix decisions.
- `terminal/`: execution mediation payloads and `exec --json` responses.
- `runtime/`: session, reply, and chat payloads needed for runtime parity checks.

## Naming

- Use lowercase snake_case file names.
- Name files for the observable behavior they capture, for example `command_fix_basic.json`.
- Keep payloads as exported JSON without hand-editing business fields after capture.
