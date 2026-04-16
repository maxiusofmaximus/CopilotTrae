from local_ai_agent.router.errors import RouterErrorEnvelope
from local_ai_agent.router.output import EnvelopeMetadata, RouteEnvelope
from local_ai_agent.router.policies import ConfidencePolicy, PolicyMaterialization


def test_policy_overrides_and_router_error_share_envelope_shape_by_composition():
    thresholds = ConfidencePolicy.defaults()
    policies = PolicyMaterialization.empty()
    route = RouteEnvelope.command_fix(
        intent="correction",
        snapshot_version="snap-1",
        original="github.cli --version",
        suggested_command="gh --version",
        evidence=["alias_match:gh"],
        confidence=0.92,
        threshold_applied=0.90,
        threshold_source="intent:command_fix",
        resolver_path=["normalize_input"],
    )
    error = RouterErrorEnvelope(
        error_code="snapshot_version_mismatch",
        request_id="req-1",
        session_id="sess-1",
        snapshot_version="snap-1",
        diagnostics={"stage": "snapshot_binding"},
    )

    assert thresholds.for_intent("execution") == 0.93
    assert "trust_policy" in policies.model_dump()
    assert error.kind == "router_error"
    assert isinstance(route.envelope, EnvelopeMetadata)
    assert isinstance(error.envelope, EnvelopeMetadata)
    assert not issubclass(RouterErrorEnvelope, RouteEnvelope)
