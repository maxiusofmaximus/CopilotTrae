from __future__ import annotations

import io

import pytest

from local_ai_agent.cli import main
from local_ai_agent.router.output import RouteEnvelope
from local_ai_agent.router.snapshot import RegistrySnapshot


class FakeRouterRuntime:
    def __init__(self, envelope: object) -> None:
        self.envelope = envelope
        self.snapshot = RegistrySnapshot.minimal(snapshot_version="snap-1", built_for_session="sess-1")

    def resolve(self, request: object) -> object:
        return self.envelope


class FakeRuntime:
    def __init__(self, envelope: object) -> None:
        self.router_runtime = FakeRouterRuntime(envelope)


def test_exec_output_formats_command_fix_with_clear_spacing(monkeypatch: pytest.MonkeyPatch):
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

    class FakeExecutor:
        def execute(self, command: str):
            raise AssertionError(f"Should not execute during UX formatting test: {command}")

    monkeypatch.setattr("local_ai_agent.cli.CommandExecutor", FakeExecutor)

    exit_code = main(["exec", "github.cli", "--version"], runtime=runtime, stdin=stdin, stdout=stdout)

    assert exit_code == 0
    assert stdout.getvalue() == (
        "Command not found.\n"
        "\n"
        "Suggested command:\n"
        "gh --version\n"
        "\n"
        "Execute suggested command? (y/n): "
    )
