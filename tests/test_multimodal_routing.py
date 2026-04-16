from local_ai_agent.multimodal import (
    ContentExpectation,
    InputRoutingPolicy,
    OCRQualityAssessment,
    RouteDecision,
    RoutingCapabilities,
    RoutingProfile,
)


def test_routing_policy_prefers_ocr_when_quality_is_acceptable_in_cost_sensitive_mode():
    policy = InputRoutingPolicy()

    decision = policy.decide_route(
        context=ContentExpectation.DOCUMENT,
        assessment=OCRQualityAssessment(
            score=0.78,
            acceptability="acceptable",
            reasons=["document_quality_pass"],
            signals={"word_count": 42, "symbol_density": 0.04},
        ),
        profile=RoutingProfile.COST_SENSITIVE,
        capabilities=RoutingCapabilities(vision_available=True),
    )

    assert isinstance(decision, RouteDecision)
    assert decision.route == "use_ocr"
    assert decision.reason == "acceptable_ocr_lower_cost"


def test_routing_policy_keeps_borderline_document_on_ocr_in_balanced_mode():
    policy = InputRoutingPolicy()
    assessment = OCRQualityAssessment(
        score=0.72,
        acceptability="borderline",
        reasons=["borderline_document_quality"],
        signals={"word_count": 42, "symbol_density": 0.04},
    )

    decision = policy.decide_route(
        context=ContentExpectation.DOCUMENT,
        assessment=assessment,
        profile=RoutingProfile.BALANCED,
        capabilities=RoutingCapabilities(vision_available=True),
    )

    assert decision.route == "use_ocr"
    assert decision.reason == "borderline_ocr_accepted_in_balanced_mode"


def test_routing_policy_escalates_same_borderline_document_in_accuracy_sensitive_mode():
    policy = InputRoutingPolicy()
    assessment = OCRQualityAssessment(
        score=0.72,
        acceptability="borderline",
        reasons=["borderline_document_quality"],
        signals={"word_count": 42, "symbol_density": 0.04},
    )

    decision = policy.decide_route(
        context=ContentExpectation.DOCUMENT,
        assessment=assessment,
        profile=RoutingProfile.ACCURACY_SENSITIVE,
        capabilities=RoutingCapabilities(vision_available=True),
    )

    assert decision.route == "escalate_to_vision"
    assert decision.reason == "accuracy_priority_overrides_borderline_ocr"


def test_routing_policy_escalates_empty_ocr_output_when_vision_is_available():
    policy = InputRoutingPolicy()

    decision = policy.decide_route(
        context=ContentExpectation.DOCUMENT,
        assessment=OCRQualityAssessment(
            score=0.05,
            acceptability="poor",
            reasons=["empty_output"],
            signals={"word_count": 0, "symbol_density": 0.0},
        ),
        profile=RoutingProfile.BALANCED,
        capabilities=RoutingCapabilities(vision_available=True),
    )

    assert decision.route == "escalate_to_vision"
    assert decision.reason == "ocr_unusable_empty_output"


def test_routing_policy_fails_when_vision_is_required_but_unavailable():
    policy = InputRoutingPolicy()

    decision = policy.decide_route(
        context=ContentExpectation.DOCUMENT,
        assessment=OCRQualityAssessment(
            score=0.05,
            acceptability="poor",
            reasons=["empty_output", "extreme_noise"],
            signals={"word_count": 0, "symbol_density": 0.9},
        ),
        profile=RoutingProfile.BALANCED,
        capabilities=RoutingCapabilities(vision_available=False),
    )

    assert decision.route == "fail"
    assert decision.reason == "vision_required_but_unavailable"
