import pytest

from local_ai_agent.router.output import EnvelopeMetadata, RouteEnvelope
from local_ai_agent.router.request import TerminalRequest


def test_invariant_resolver_path_only_contains_executed_steps():
    from local_ai_agent.router.invariants import assert_resolver_path_matches_route

    envelope = RouteEnvelope.command_fix(
        intent="correction",
        snapshot_version="snap-1",
        original="github.cli --version",
        suggested_command="gh --version",
        evidence=["alias_match:github-cli"],
        confidence=1.0,
        threshold_applied=0.90,
        threshold_source="intent:command_fix",
        resolver_path=[
            "normalize_input",
            "parse_command_shape",
            "classify_intent",
            "resolve_local_candidates",
            "apply_deterministic_rules",
            "fixes.collect_alias_matches",
            "fixes.rank_candidates",
            "evaluate_confidence",
        ],
    )

    assert_resolver_path_matches_route(envelope)


def test_invariant_command_and_argv_match_semantically():
    from local_ai_agent.router.invariants import assert_command_matches_argv

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

    assert_command_matches_argv(command="gh --version", envelope=envelope)


def test_invariant_tool_execution_rejects_disallowed_execution_policy():
    from local_ai_agent.router.invariants import assert_execution_policy_allows_route

    envelope = RouteEnvelope(
        envelope=EnvelopeMetadata(kind="route", snapshot_version="snap-1"),
        route="tool_execution",
        intent="tool_execution",
        payload={
            "tool_name": "gh",
            "shell": "powershell",
            "argv": ["gh", "--version"],
            "execution_policy": {"allowed": False},
        },
        evidence=["tool_name_match:gh"],
        confidence=1.0,
        threshold_applied=0.93,
        threshold_source="intent:execution",
        resolver_path=["normalize_input", "evaluate_confidence"],
    )

    with pytest.raises(AssertionError, match="execution_policy.allowed=false"):
        assert_execution_policy_allows_route(envelope)


def test_invariant_external_escalation_requires_capability_and_policy():
    from local_ai_agent.router.invariants import assert_external_escalation_is_authorized

    envelope = RouteEnvelope(
        envelope=EnvelopeMetadata(kind="route", snapshot_version="snap-1"),
        route="hub_action_proposal",
        intent="installation",
        payload={"proposal": {"action": "open_hub", "target": "ripgrep"}},
        evidence=["operator_confirmation_required"],
        confidence=0.80,
        threshold_applied=0.85,
        threshold_source="intent:installation",
        resolver_path=["normalize_input", "evaluate_capability_gap"],
    )

    with pytest.raises(AssertionError, match="capability and policy"):
        assert_external_escalation_is_authorized(
            envelope,
            capability_surface={"capabilities": ()},
            policies={},
        )


def test_invariant_request_and_output_snapshot_versions_match():
    from local_ai_agent.router.invariants import assert_snapshot_versions_match

    request = TerminalRequest(
        request_id="req-1",
        session_id="sess-1",
        shell="powershell",
        raw_input="gh --version",
        cwd="C:\\repo",
        snapshot_version="snap-1",
    )
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

    assert_snapshot_versions_match(request, envelope)


def test_invariant_clarification_returns_serialized_options():
    from local_ai_agent.router.invariants import assert_clarification_options_are_serialized

    envelope = RouteEnvelope.clarification(
        intent="correction",
        snapshot_version="snap-1",
        original="tool.cli --version",
        options=["tool --version", "mytool --version"],
        evidence=["suffix_match:tool-cli"],
        confidence=0.9,
        threshold_applied=0.9,
        threshold_source="intent:command_fix",
        resolver_path=["normalize_input", "fixes.rank_candidates"],
    )

    assert_clarification_options_are_serialized(envelope)
