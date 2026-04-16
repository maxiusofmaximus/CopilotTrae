from __future__ import annotations

from collections.abc import Mapping

from local_ai_agent.router.output import RouteEnvelope
from local_ai_agent.router.request import TerminalRequest


def assert_resolver_path_matches_route(envelope: RouteEnvelope) -> None:
    allowed: set[str] = {"normalize_input", "parse_command_shape", "classify_intent", "evaluate_confidence"}
    if envelope.route == "tool_execution":
        allowed |= {"resolve_local_candidates", "apply_deterministic_rules"}
        forbidden = {step for step in envelope.resolver_path if step.startswith("fixes.")}
        assert not forbidden, f"tool_execution cannot include fix engine steps: {sorted(forbidden)}"
    if envelope.route == "command_fix":
        allowed |= {"resolve_local_candidates", "apply_deterministic_rules"}
        allowed |= {
            "fixes.collect_alias_matches",
            "fixes.collect_suffix_matches",
            "fixes.rank_candidates",
        }
    if envelope.route == "clarification":
        allowed |= {"resolve_local_candidates", "apply_deterministic_rules"}
        allowed |= {
            "fixes.collect_alias_matches",
            "fixes.collect_suffix_matches",
            "fixes.rank_candidates",
        }
    if envelope.route in {"hub_install", "hub_action_proposal"}:
        allowed |= {"evaluate_capability_gap"}

    unknown = [step for step in envelope.resolver_path if step not in allowed]
    assert not unknown, f"resolver_path has steps not executed by this route: {unknown}"


def assert_command_matches_argv(*, command: str, envelope: RouteEnvelope) -> None:
    # Invariants only apply when argv is part of the output surface.
    argv = envelope.payload.get("argv")
    if argv is None:
        return
    assert isinstance(argv, list), "payload.argv must be a list when present"
    assert argv, "payload.argv cannot be empty when present"

    normalized_command = " ".join(command.strip().split())
    normalized_argv = " ".join(str(item).strip() for item in argv if str(item).strip())
    assert normalized_argv == normalized_command, f"command and argv mismatch: {normalized_command!r} vs {normalized_argv!r}"


def assert_execution_policy_allows_route(envelope: RouteEnvelope) -> None:
    if envelope.route != "tool_execution":
        return
    policy = envelope.payload.get("execution_policy")
    if policy is None:
        return
    assert isinstance(policy, Mapping), "execution_policy must be a mapping"
    allowed = policy.get("allowed", True)
    assert allowed is not False, "execution_policy.allowed=false forbids tool_execution"


def assert_external_escalation_is_authorized(
    envelope: RouteEnvelope,
    *,
    capability_surface: Mapping[str, object],
    policies: Mapping[str, object],
) -> None:
    if envelope.route not in {"hub_install", "hub_action_proposal"}:
        return
    capabilities = capability_surface.get("capabilities", ())
    allowed = policies.get("allow_external_escalation", False)
    assert "hub_access" in capabilities and allowed is True, "external escalation requires capability and policy"


def assert_snapshot_versions_match(request: TerminalRequest, envelope: RouteEnvelope) -> None:
    assert request.snapshot_version == envelope.snapshot_version, "request.snapshot_version must equal output.snapshot_version"


def assert_clarification_options_are_serialized(envelope: RouteEnvelope) -> None:
    if envelope.route != "clarification":
        return
    options = envelope.payload.get("options")
    assert isinstance(options, list), "clarification payload.options must be a list"
    assert all(isinstance(item, str) for item in options), "clarification payload.options must be list[str]"
