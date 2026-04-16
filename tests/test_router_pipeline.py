from local_ai_agent.router.errors import RouterErrorEnvelope
from local_ai_agent.router.pipeline import DeterministicRouter
from local_ai_agent.router.request import TerminalRequest
from local_ai_agent.router.snapshot import RegistrySnapshot


def test_router_emits_tool_execution_using_snapshot_only():
    snapshot = RegistrySnapshot(
        snapshot_version="snap-1",
        built_for_session="sess-1",
        execution_surface={
            "tools": [
                {
                    "tool_name": "gh",
                    "adapter_name": "generic_cli",
                    "shell": "powershell",
                    "available": True,
                    "aliases": ["github"],
                    "capabilities": ["version"],
                }
            ]
        },
        capability_surface={"capabilities": ("tool_execution", "command_fix")},
    )
    router = DeterministicRouter()
    request = TerminalRequest(
        request_id="req-1",
        session_id="sess-1",
        shell="powershell",
        raw_input="gh --version",
        cwd="C:\\repo",
        snapshot_version="snap-1",
    )

    result = router.resolve(request, snapshot)

    assert result.route == "tool_execution"
    assert result.payload["tool_name"] == "gh"
    assert result.payload["argv"] == ["gh", "--version"]
    assert result.resolver_path == [
        "normalize_input",
        "parse_command_shape",
        "classify_intent",
        "resolve_local_candidates",
        "apply_deterministic_rules",
        "evaluate_confidence",
    ]


def test_router_returns_router_error_envelope_for_snapshot_version_mismatch():
    snapshot = RegistrySnapshot.minimal(
        snapshot_version="snap-active",
        built_for_session="sess-1",
    )
    router = DeterministicRouter()
    request = TerminalRequest(
        request_id="req-2",
        session_id="sess-1",
        shell="powershell",
        raw_input="gh --version",
        cwd="C:\\repo",
        snapshot_version="snap-stale",
    )

    result = router.resolve(request, snapshot)

    assert isinstance(result, RouterErrorEnvelope)
    assert result.error_code == "snapshot_version_mismatch"
    assert result.snapshot_version == "snap-active"
