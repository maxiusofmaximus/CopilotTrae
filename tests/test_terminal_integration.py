from __future__ import annotations

import io
import json

import pytest

from local_ai_agent.cli import main
from local_ai_agent.router.output import EnvelopeMetadata, RouteEnvelope
from local_ai_agent.router.snapshot import RegistrySnapshot
from local_ai_agent.terminal.executor import ExecutionResult


class FakeRouterRuntime:
    def __init__(self, envelope: object) -> None:
        self.envelope = envelope
        self.snapshot = RegistrySnapshot.minimal(snapshot_version="snap-1", built_for_session="sess-1")
        self.calls: list[object] = []

    def resolve(self, request: object) -> object:
        self.calls.append(request)
        return self.envelope


class FakeRuntime:
    def __init__(self, envelope: object) -> None:
        self.router_runtime = FakeRouterRuntime(envelope)


def test_cli_exec_executes_tool_execution_command(monkeypatch: pytest.MonkeyPatch):
    envelope = RouteEnvelope.tool_execution(
        intent="tool_execution",
        snapshot_version="snap-1",
        tool_name="gh",
        shell="powershell",
        argv=["gh", "--version"],
        confidence=1.0,
        threshold_applied=0.93,
        threshold_source="intent:execution",
        resolver_path=["normalize_input", "evaluate_confidence"],
        evidence=["tool_name_match:gh"],
    )
    runtime = FakeRuntime(envelope)
    stdout = io.StringIO()
    stdin = io.StringIO("")
    executed: list[str] = []

    class FakeExecutor:
        def execute(self, command: str) -> ExecutionResult:
            executed.append(command)
            return ExecutionResult(command=command, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("local_ai_agent.cli.CommandExecutor", FakeExecutor)

    exit_code = main(["exec", "gh", "--version"], runtime=runtime, stdin=stdin, stdout=stdout)

    assert exit_code == 0
    assert executed == ["gh --version"]
    assert "Executed" in stdout.getvalue()


def test_cli_exec_suggests_correction_and_does_not_execute_when_user_declines(monkeypatch: pytest.MonkeyPatch):
    envelope = RouteEnvelope.command_fix(
        intent="correction",
        snapshot_version="snap-1",
        original="github.cli --version",
        suggested_command="gh --version",
        evidence=["alias_match:github-cli"],
        confidence=1.0,
        threshold_applied=0.90,
        threshold_source="intent:command_fix",
        resolver_path=["normalize_input", "fixes.rank_candidates", "evaluate_confidence"],
    )
    runtime = FakeRuntime(envelope)
    stdout = io.StringIO()
    stdin = io.StringIO("n\n")
    executed: list[str] = []

    class FakeExecutor:
        def execute(self, command: str) -> ExecutionResult:
            executed.append(command)
            return ExecutionResult(command=command, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("local_ai_agent.cli.CommandExecutor", FakeExecutor)

    exit_code = main(["exec", "github.cli", "--version"], runtime=runtime, stdin=stdin, stdout=stdout)

    assert exit_code == 0
    assert executed == []
    assert "Suggested" in stdout.getvalue()


def test_cli_exec_runs_suggested_command_fix_only_when_user_confirms(monkeypatch: pytest.MonkeyPatch):
    envelope = RouteEnvelope.command_fix(
        intent="correction",
        snapshot_version="snap-1",
        original="github.cli --version",
        suggested_command="gh --version",
        evidence=["alias_match:github-cli"],
        confidence=1.0,
        threshold_applied=0.90,
        threshold_source="intent:command_fix",
        resolver_path=["normalize_input", "fixes.rank_candidates", "evaluate_confidence"],
    )
    runtime = FakeRuntime(envelope)
    stdout = io.StringIO()
    stdin = io.StringIO("y\n")
    executed: list[str] = []

    class FakeExecutor:
        def execute(self, command: str) -> ExecutionResult:
            executed.append(command)
            return ExecutionResult(command=command, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("local_ai_agent.cli.CommandExecutor", FakeExecutor)

    exit_code = main(["exec", "github.cli", "--version"], runtime=runtime, stdin=stdin, stdout=stdout)

    assert exit_code == 0
    assert executed == ["gh --version"]
    assert "Execute suggested" in stdout.getvalue() or "Execute" in stdout.getvalue()


def test_cli_exec_policy_denied_blocks_execution(monkeypatch: pytest.MonkeyPatch):
    envelope = RouteEnvelope(
        envelope=EnvelopeMetadata(kind="route", snapshot_version="snap-1"),
        route="policy_denied",
        intent="tool_execution",
        payload={"reason": "blocked by trust policy"},
        evidence=["policy:strict"],
        confidence=1.0,
        threshold_applied=1.0,
        threshold_source="policy:block",
        resolver_path=["normalize_input", "apply_deterministic_rules"],
    )
    runtime = FakeRuntime(envelope)
    stdout = io.StringIO()
    stdin = io.StringIO("")
    executed: list[str] = []

    class FakeExecutor:
        def execute(self, command: str) -> ExecutionResult:
            executed.append(command)
            return ExecutionResult(command=command, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("local_ai_agent.cli.CommandExecutor", FakeExecutor)

    exit_code = main(["exec", "gh", "auth", "login"], runtime=runtime, stdin=stdin, stdout=stdout)

    assert exit_code != 0
    assert executed == []
    assert "blocked" in stdout.getvalue().lower()


def test_cli_exec_yes_executes_suggested_command_without_prompt(monkeypatch: pytest.MonkeyPatch):
    envelope = RouteEnvelope.command_fix(
        intent="correction",
        snapshot_version="snap-1",
        original="github.cli --version",
        suggested_command="gh --version",
        evidence=["alias_match:github-cli"],
        confidence=1.0,
        threshold_applied=0.90,
        threshold_source="intent:command_fix",
        resolver_path=["normalize_input", "fixes.rank_candidates", "evaluate_confidence"],
    )
    runtime = FakeRuntime(envelope)
    stdout = io.StringIO()
    stdin = io.StringIO("")
    executed: list[str] = []

    class FakeExecutor:
        def execute(self, command: str) -> ExecutionResult:
            executed.append(command)
            return ExecutionResult(command=command, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("local_ai_agent.cli.CommandExecutor", FakeExecutor)

    exit_code = main(
        ["exec", "github.cli", "--version", "--yes"],
        runtime=runtime,
        stdin=stdin,
        stdout=stdout,
    )

    assert exit_code == 0
    assert executed == ["gh --version"]
    assert "Execute suggested command? (y/n):" not in stdout.getvalue()


def test_cli_exec_dry_run_shows_suggestion_without_prompt_or_execution(monkeypatch: pytest.MonkeyPatch):
    envelope = RouteEnvelope.command_fix(
        intent="correction",
        snapshot_version="snap-1",
        original="github.cli --version",
        suggested_command="gh --version",
        evidence=["alias_match:github-cli"],
        confidence=1.0,
        threshold_applied=0.90,
        threshold_source="intent:command_fix",
        resolver_path=["normalize_input", "fixes.rank_candidates", "evaluate_confidence"],
    )
    runtime = FakeRuntime(envelope)
    stdout = io.StringIO()
    stdin = io.StringIO("")
    executed: list[str] = []

    class FakeExecutor:
        def execute(self, command: str) -> ExecutionResult:
            executed.append(command)
            return ExecutionResult(command=command, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("local_ai_agent.cli.CommandExecutor", FakeExecutor)

    exit_code = main(
        ["exec", "github.cli", "--version", "--dry-run"],
        runtime=runtime,
        stdin=stdin,
        stdout=stdout,
    )

    assert exit_code == 0
    assert executed == []
    assert "Suggested command:\ngh --version" in stdout.getvalue()
    assert "Execute suggested command? (y/n):" not in stdout.getvalue()
    assert "Dry-run: no commands executed." in stdout.getvalue()


def test_cli_exec_json_prints_only_serialized_route_envelope(monkeypatch: pytest.MonkeyPatch):
    envelope = RouteEnvelope.command_fix(
        intent="correction",
        snapshot_version="snap-1",
        original="github.cli --version",
        suggested_command="gh --version",
        evidence=["alias_match:github-cli"],
        confidence=1.0,
        threshold_applied=0.90,
        threshold_source="intent:command_fix",
        resolver_path=["normalize_input", "fixes.rank_candidates", "evaluate_confidence"],
    )
    runtime = FakeRuntime(envelope)
    stdout = io.StringIO()
    stdin = io.StringIO("")
    executed: list[str] = []

    class FakeExecutor:
        def execute(self, command: str) -> ExecutionResult:
            executed.append(command)
            return ExecutionResult(command=command, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("local_ai_agent.cli.CommandExecutor", FakeExecutor)

    exit_code = main(
        ["exec", "github.cli", "--version", "--json", "--yes", "--dry-run"],
        runtime=runtime,
        stdin=stdin,
        stdout=stdout,
    )

    assert exit_code == 0
    assert executed == []
    payload = json.loads(stdout.getvalue())
    assert payload["route"] == "command_fix"
    assert payload["payload"]["suggested_command"] == "gh --version"
    assert "Command not found." not in stdout.getvalue()


def test_cli_exec_debug_writes_route_and_host_decision_without_polluting_stdout(monkeypatch: pytest.MonkeyPatch):
    envelope = RouteEnvelope.command_fix(
        intent="correction",
        snapshot_version="snap-1",
        original="github.cli --version",
        suggested_command="gh --version",
        evidence=["alias_match:github-cli"],
        confidence=1.0,
        threshold_applied=0.90,
        threshold_source="intent:command_fix",
        resolver_path=["normalize_input", "fixes.rank_candidates", "evaluate_confidence"],
    )
    runtime = FakeRuntime(envelope)
    stdout = io.StringIO()
    stderr = io.StringIO()
    stdin = io.StringIO("n\n")

    class FakeExecutor:
        def execute(self, command: str) -> ExecutionResult:
            raise AssertionError(f"Should not execute during debug test: {command}")

    monkeypatch.setattr("local_ai_agent.cli.CommandExecutor", FakeExecutor)

    exit_code = main(
        ["exec", "github.cli", "--version", "--debug"],
        runtime=runtime,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert "Command not found." in stdout.getvalue()
    assert "route=command_fix" in stderr.getvalue()
    assert "host_action=suggest_correction" in stderr.getvalue()
    assert '"route": "command_fix"' in stderr.getvalue()


def test_cli_exec_normalizes_trailing_flags_from_sys_argv(monkeypatch: pytest.MonkeyPatch):
    envelope = RouteEnvelope.command_fix(
        intent="correction",
        snapshot_version="snap-1",
        original="github.cli --version",
        suggested_command="gh --version",
        evidence=["alias_match:github-cli"],
        confidence=1.0,
        threshold_applied=0.90,
        threshold_source="intent:command_fix",
        resolver_path=["normalize_input", "fixes.rank_candidates", "evaluate_confidence"],
    )
    runtime = FakeRuntime(envelope)
    stdout = io.StringIO()
    stdin = io.StringIO("")
    executed: list[str] = []

    class FakeExecutor:
        def execute(self, command: str) -> ExecutionResult:
            executed.append(command)
            return ExecutionResult(command=command, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("local_ai_agent.cli.CommandExecutor", FakeExecutor)
    monkeypatch.setattr(
        "sys.argv",
        ["local-ai-agent", "exec", "github.cli", "--version", "--yes"],
    )

    exit_code = main(runtime=runtime, stdin=stdin, stdout=stdout)

    assert exit_code == 0
    assert executed == ["gh --version"]
