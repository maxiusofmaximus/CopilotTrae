from local_ai_agent.router.fixes import CommandFixEngine
from local_ai_agent.router.pipeline import DeterministicRouter
from local_ai_agent.router.request import TerminalRequest
from local_ai_agent.router.snapshot import RegistrySnapshot


def test_command_fix_degrades_to_clarification_when_multiple_candidates_tie():
    engine = CommandFixEngine()

    result = engine.build_fix(
        raw_input="tool.cli --version",
        tools=[
            {"tool_name": "mytool", "aliases": ["tool-cli"]},
            {"tool_name": "tool", "aliases": ["tool-cli"]},
        ],
        threshold=0.90,
    )

    assert result.route == "clarification"
    assert len(result.payload["options"]) == 2


def test_command_fix_only_uses_snapshot_tools_and_tracks_real_resolver_path():
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
                    "aliases": ["github-cli"],
                    "capabilities": ["version"],
                }
            ]
        },
        capability_surface={"capabilities": ("tool_execution", "command_fix")},
    )
    router = DeterministicRouter()
    request = TerminalRequest(
        request_id="req-3",
        session_id="sess-1",
        shell="powershell",
        raw_input="github.cli --version",
        cwd="C:\\repo",
        snapshot_version="snap-1",
    )

    result = router.resolve(request, snapshot)

    assert result.route == "command_fix"
    assert result.payload["suggested_command"] == "gh --version"
    assert "git" not in result.payload["suggested_command"]
    assert result.resolver_path == [
        "normalize_input",
        "parse_command_shape",
        "classify_intent",
        "resolve_local_candidates",
        "apply_deterministic_rules",
        "fixes.collect_alias_matches",
        "fixes.collect_suffix_matches",
        "fixes.rank_candidates",
        "evaluate_confidence",
    ]
