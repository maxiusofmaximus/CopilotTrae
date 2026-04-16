from dataclasses import FrozenInstanceError

import pytest

from local_ai_agent.router.output import RouteEnvelope
from local_ai_agent.router.request import TerminalRequest
from local_ai_agent.router.snapshot import RegistrySnapshot


def test_router_contract_models_round_trip_minimal_json():
    request = TerminalRequest(
        request_id="req-1",
        session_id="sess-1",
        shell="powershell",
        raw_input="gh --version",
        cwd="C:\\repo",
        snapshot_version="snap-1",
    )
    snapshot = RegistrySnapshot.minimal(
        snapshot_version="snap-1",
        built_for_session="sess-1",
    )
    envelope = RouteEnvelope.command_fix(
        intent="correction",
        snapshot_version="snap-1",
        original="github.cli --version",
        suggested_command="gh --version",
        evidence=["alias_match:gh"],
        confidence=0.92,
        threshold_applied=0.90,
        threshold_source="intent:command_fix",
        resolver_path=["normalize_input", "resolve_local_candidates"],
    )

    assert request.snapshot_version == snapshot.snapshot_version
    assert envelope.route == "command_fix"
    assert envelope.payload["suggested_command"] == "gh --version"


def test_terminal_request_defaults_env_visible_to_empty_dict_and_snapshot_is_deeply_immutable():
    request = TerminalRequest(
        request_id="req-2",
        session_id="sess-2",
        shell="powershell",
        raw_input="git status",
        cwd="C:\\repo",
        snapshot_version="snap-2",
    )
    snapshot = RegistrySnapshot(
        snapshot_version="snap-2",
        built_for_session="sess-2",
        tools=[{"tool_name": "gh", "aliases": ["github"]}],
        modules=[{"module_name": "github"}],
        policies={"trust_policy": {"mode": "strict"}},
    )

    assert request.env_visible == {}
    assert isinstance(snapshot.tools, tuple)

    with pytest.raises(FrozenInstanceError):
        snapshot.snapshot_version = "snap-3"

    with pytest.raises(TypeError):
        snapshot.tools[0]["tool_name"] = "git"

    with pytest.raises(TypeError):
        snapshot.policies["trust_policy"]["mode"] = "interactive"
