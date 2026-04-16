from local_ai_agent.multimodal import (
    ContentExpectation,
    OCRQualityAssessment,
    OCRResult,
    OCRScorer,
    RoutingProfile,
)


def test_ocr_scorer_accepts_short_high_confidence_ui_text():
    scorer = OCRScorer()

    result = scorer.score(
        OCRResult(
            text="Save",
            mean_confidence=0.97,
            token_confidences=[0.98, 0.96],
            elapsed_ms=12,
        ),
        context=ContentExpectation.UI_TEXT,
        profile=RoutingProfile.BALANCED,
    )

    assert isinstance(result, OCRQualityAssessment)
    assert result.score >= 0.75
    assert result.acceptability == "acceptable"
    assert "short_text_allowed_for_ui" in result.reasons


def test_ocr_scorer_rejects_short_document_text():
    scorer = OCRScorer()

    result = scorer.score(
        OCRResult(
            text="Total",
            mean_confidence=0.98,
            token_confidences=[0.98],
            elapsed_ms=20,
        ),
        context=ContentExpectation.DOCUMENT,
        profile=RoutingProfile.BALANCED,
    )

    assert result.acceptability == "poor"
    assert "insufficient_document_coverage" in result.reasons


def test_ocr_scorer_tolerates_symbol_density_for_code_images():
    scorer = OCRScorer()

    result = scorer.score(
        OCRResult(
            text="if (x == y) { return z; }",
            mean_confidence=0.79,
            token_confidences=[0.8, 0.77, 0.81],
            elapsed_ms=18,
        ),
        context=ContentExpectation.CODE_IMAGE,
        profile=RoutingProfile.BALANCED,
    )

    assert result.score >= 0.6
    assert "symbol_density_tolerated_for_code" in result.reasons


def test_ocr_scorer_marks_empty_output_as_unusable():
    scorer = OCRScorer()

    result = scorer.score(
        OCRResult(
            text="   ",
            mean_confidence=0.18,
            token_confidences=[],
            elapsed_ms=11,
        ),
        context=ContentExpectation.DOCUMENT,
        profile=RoutingProfile.BALANCED,
    )

    assert result.acceptability == "poor"
    assert "empty_output" in result.reasons
    assert result.signals["word_count"] == 0
