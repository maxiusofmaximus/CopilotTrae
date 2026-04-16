from pathlib import Path

import pytest

from local_ai_agent.multimodal import (
    ContentExpectation,
    MultimodalInputProcessor,
    MultimodalProcessingError,
    OCRQualityAssessment,
    OCRResult,
    ProcessedInput,
    RouteDecision,
    RoutingProfile,
    VisionResult,
)


def test_processor_uses_ocr_text_when_routing_accepts_it(tmp_path: Path):
    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"fake")
    events: list[str] = []

    class FakeOCRExtractor:
        @property
        def resolved_command_path(self) -> str:
            return str(tmp_path / "bin" / "tesseract" / "tesseract.exe")

        def extract(self, file_path: Path) -> OCRResult:
            events.append(f"ocr:{file_path.name}")
            return OCRResult(text="  Save  ", mean_confidence=0.97, token_confidences=[0.97], elapsed_ms=10)

    class FakeScorer:
        def score(self, result: OCRResult, context: ContentExpectation, profile: RoutingProfile) -> OCRQualityAssessment:
            events.append(f"score:{context.value}:{profile.value}:{result.text.strip()}")
            return OCRQualityAssessment(
                score=0.9,
                acceptability="acceptable",
                reasons=["ui_quality_pass"],
                signals={"word_count": 1, "symbol_density": 0.0},
            )

    class FakeRoutingPolicy:
        def decide_route(self, context, assessment, profile, capabilities) -> RouteDecision:
            events.append(f"route:{context.value}:{assessment.acceptability}:{capabilities.vision_available}")
            return RouteDecision(
                route="use_ocr",
                reason="acceptable_ocr_lower_cost",
                quality_gap=0.0,
                cost_justification="prefer_lower_cost_path",
            )

    processor = MultimodalInputProcessor(
        ocr_extractor=FakeOCRExtractor(),
        scorer=FakeScorer(),
        routing_policy=FakeRoutingPolicy(),
        vision_interpreter=None,
    )

    processed = processor.process(image_path, context=ContentExpectation.UI_TEXT)

    assert isinstance(processed, ProcessedInput)
    assert processed.text == "Save"
    assert processed.route_taken == "use_ocr"
    assert processed.metadata["routing_reason"] == "acceptable_ocr_lower_cost"
    assert processed.metadata["ocr_score"] == 0.9
    assert processed.metadata["context"] == "ui_text"
    assert processed.metadata["ocr_binary_path"].endswith(r"bin\tesseract\tesseract.exe")
    assert events == [
        "ocr:screen.png",
        "score:ui_text:balanced:Save",
        "route:ui_text:acceptable:False",
    ]


def test_processor_calls_vision_only_after_routing_escalates(tmp_path: Path):
    image_path = tmp_path / "diagram.png"
    image_path.write_bytes(b"fake")
    events: list[str] = []

    class FakeOCRExtractor:
        def extract(self, file_path: Path) -> OCRResult:
            events.append(f"ocr:{file_path.name}")
            return OCRResult(text="   ", mean_confidence=0.1, token_confidences=[0.1], elapsed_ms=12)

    class FakeScorer:
        def score(self, result: OCRResult, context: ContentExpectation, profile: RoutingProfile) -> OCRQualityAssessment:
            events.append(f"score:{context.value}:{profile.value}")
            return OCRQualityAssessment(
                score=0.1,
                acceptability="poor",
                reasons=["empty_output"],
                signals={"word_count": 0, "symbol_density": 0.0},
            )

    class FakeRoutingPolicy:
        def decide_route(self, context, assessment, profile, capabilities) -> RouteDecision:
            events.append(f"route:{context.value}:{assessment.acceptability}:{capabilities.vision_available}")
            return RouteDecision(
                route="escalate_to_vision",
                reason="ocr_unusable_empty_output",
                quality_gap=0.9,
                cost_justification="quality_gap_justifies_escalation",
            )

    class FakeVisionInterpreter:
        def interpret(self, file_path: Path, context: ContentExpectation) -> VisionResult:
            events.append(f"vision:{file_path.name}:{context.value}")
            return VisionResult(
                text="  A diagram showing a payment workflow.  ",
                provider="fake-vision",
                model="vision-model",
            )

    processor = MultimodalInputProcessor(
        ocr_extractor=FakeOCRExtractor(),
        scorer=FakeScorer(),
        routing_policy=FakeRoutingPolicy(),
        vision_interpreter=FakeVisionInterpreter(),
    )

    processed = processor.process(image_path, context=ContentExpectation.DOCUMENT)

    assert processed.text == "A diagram showing a payment workflow."
    assert processed.route_taken == "escalate_to_vision"
    assert processed.metadata["routing_reason"] == "ocr_unusable_empty_output"
    assert processed.metadata["vision_provider"] == "fake-vision"
    assert processed.metadata["vision_model"] == "vision-model"
    assert events == [
        "ocr:diagram.png",
        "score:document:balanced",
        "route:document:poor:True",
        "vision:diagram.png:document",
    ]


def test_processor_raises_explicit_error_when_vision_is_required_but_unavailable(tmp_path: Path):
    image_path = tmp_path / "invoice.png"
    image_path.write_bytes(b"fake")
    events: list[str] = []

    class FakeOCRExtractor:
        @property
        def resolved_command_path(self) -> str:
            return str(tmp_path / "bin" / "tesseract" / "tesseract.exe")

        def extract(self, file_path: Path) -> OCRResult:
            events.append(f"ocr:{file_path.name}")
            return OCRResult(text="", mean_confidence=0.05, token_confidences=[0.05], elapsed_ms=9)

    class FakeScorer:
        def score(self, result: OCRResult, context: ContentExpectation, profile: RoutingProfile) -> OCRQualityAssessment:
            events.append(f"score:{context.value}:{profile.value}")
            return OCRQualityAssessment(
                score=0.05,
                acceptability="poor",
                reasons=["empty_output", "extreme_noise"],
                signals={"word_count": 0, "symbol_density": 0.8},
            )

    class FakeRoutingPolicy:
        def decide_route(self, context, assessment, profile, capabilities) -> RouteDecision:
            events.append(f"route:{context.value}:{assessment.acceptability}:{capabilities.vision_available}")
            return RouteDecision(
                route="fail",
                reason="vision_required_but_unavailable",
                quality_gap=0.95,
                cost_justification="missing_vision_capability",
            )

    processor = MultimodalInputProcessor(
        ocr_extractor=FakeOCRExtractor(),
        scorer=FakeScorer(),
        routing_policy=FakeRoutingPolicy(),
        vision_interpreter=None,
    )

    with pytest.raises(MultimodalProcessingError, match="vision_required_but_unavailable") as exc_info:
        processor.process(image_path, context=ContentExpectation.DOCUMENT)

    assert exc_info.value.metadata is not None
    assert exc_info.value.metadata["ocr_binary_path"].endswith(r"bin\tesseract\tesseract.exe")
    assert events == [
        "ocr:invoice.png",
        "score:document:balanced",
        "route:document:poor:False",
    ]
