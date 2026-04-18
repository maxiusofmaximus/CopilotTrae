from __future__ import annotations

from local_ai_agent.terminal.executor import ExecutionResult
from local_ai_agent.router.output import EnvelopeMetadata, RouteEnvelope
from local_ai_agent.router.snapshot import RegistrySnapshot


class FakeRouterRuntime:
    def __init__(self, result: object) -> None:
        self.result = result
        self.snapshot = RegistrySnapshot.minimal(
            snapshot_version="snap-1",
            built_for_session="sess-1",
        )
        self.calls: list[object] = []

    def resolve(self, request: object) -> object:
        self.calls.append(request)
        return self.result


class FakeExecutor:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def execute(self, command: str):
        self.commands.append(command)
        return ExecutionResult(command=command, returncode=0, stdout="ok", stderr="")


def test_terminal_host_command_fix_does_not_execute_automatically():
    from local_ai_agent.terminal.host import TerminalHost

    envelope = RouteEnvelope.command_fix(
        intent="correction",
        snapshot_version="snap-1",
        original="github.cli --version",
        suggested_command="gh --version",
        evidence=["alias_match:gh"],
        confidence=0.95,
        threshold_applied=0.90,
        threshold_source="intent:command_fix",
        resolver_path=["normalize_input", "fixes.rank_candidates", "evaluate_confidence"],
    )
    executor = FakeExecutor()
    host = TerminalHost(
        router_runtime=FakeRouterRuntime(envelope),
        executor=executor,
        session_id="sess-1",
        shell="powershell",
        cwd="C:\\repo",
        request_id_factory=lambda: "req-1",
    )

    result = host.handle_input("github.cli --version")

    assert result.route == "command_fix"
    assert result.action == "suggest_correction"
    assert result.suggested_command == "gh --version"
    assert result.can_execute_suggested_command is True
    assert executor.commands == []


def test_terminal_host_tool_execution_runs_when_allowed():
    from local_ai_agent.terminal.host import TerminalHost

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
    executor = FakeExecutor()
    host = TerminalHost(
        router_runtime=FakeRouterRuntime(envelope),
        executor=executor,
        session_id="sess-1",
        shell="powershell",
        cwd="C:\\repo",
        request_id_factory=lambda: "req-2",
    )

    result = host.handle_input("gh --version")

    assert result.route == "tool_execution"
    assert result.action == "executed"
    assert result.executed_command == "gh --version"
    assert result.execution_result.returncode == 0
    assert executor.commands == ["gh --version"]


def test_terminal_host_tool_execution_blocks_when_argv_is_empty():
    from local_ai_agent.terminal.host import TerminalHost

    envelope = RouteEnvelope(
        envelope=EnvelopeMetadata(kind="route", snapshot_version="snap-1"),
        route="tool_execution",
        intent="tool_execution",
        payload={"tool_name": "python", "shell": "powershell", "argv": []},
        evidence=["tool_name_match:python"],
        confidence=1.0,
        threshold_applied=0.93,
        threshold_source="intent:execution",
        resolver_path=["normalize_input", "evaluate_confidence"],
    )
    executor = FakeExecutor()
    host = TerminalHost(
        router_runtime=FakeRouterRuntime(envelope),
        executor=executor,
        session_id="sess-1",
        shell="powershell",
        cwd="C:\\repo",
        request_id_factory=lambda: "req-empty",
    )

    result = host.handle_input("python -v")

    assert result.route == "tool_execution"
    assert result.action == "blocked"
    assert result.blocked_reason == "empty_command"
    assert executor.commands == []


def test_terminal_host_policy_denied_blocks_execution():
    from local_ai_agent.terminal.host import TerminalHost

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
    executor = FakeExecutor()
    host = TerminalHost(
        router_runtime=FakeRouterRuntime(envelope),
        executor=executor,
        session_id="sess-1",
        shell="powershell",
        cwd="C:\\repo",
        request_id_factory=lambda: "req-3",
    )

    result = host.handle_input("gh auth login")

    assert result.route == "policy_denied"
    assert result.action == "blocked"
    assert result.blocked_reason == "blocked by trust policy"
    assert executor.commands == []


def test_terminal_host_clarification_returns_visible_options():
    from local_ai_agent.terminal.host import TerminalHost

    envelope = RouteEnvelope.clarification(
        intent="correction",
        snapshot_version="snap-1",
        original="tool.cli --version",
        options=["tool --version", "mytool --version"],
        evidence=["suffix_match:tool-cli"],
        confidence=0.91,
        threshold_applied=0.90,
        threshold_source="intent:command_fix",
        resolver_path=["normalize_input", "fixes.rank_candidates", "evaluate_confidence"],
    )
    host = TerminalHost(
        router_runtime=FakeRouterRuntime(envelope),
        executor=FakeExecutor(),
        session_id="sess-1",
        shell="powershell",
        cwd="C:\\repo",
        request_id_factory=lambda: "req-4",
    )

    result = host.handle_input("tool.cli --version")

    assert result.route == "clarification"
    assert result.action == "clarify"
    assert result.options == ["tool --version", "mytool --version"]
    assert "tool --version" in result.message
