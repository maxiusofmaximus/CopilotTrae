from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field


class ContentExpectation(str, Enum):
    DOCUMENT = "document"
    CODE_IMAGE = "code_image"
    UI_TEXT = "ui_text"


class RoutingProfile(str, Enum):
    COST_SENSITIVE = "cost_sensitive"
    BALANCED = "balanced"
    ACCURACY_SENSITIVE = "accuracy_sensitive"


class OCRResult(BaseModel):
    text: str
    mean_confidence: float | None = None
    token_confidences: list[float] = Field(default_factory=list)
    elapsed_ms: int | None = None
    engine_name: str | None = None


class OCRQualityAssessment(BaseModel):
    score: float
    acceptability: str
    reasons: list[str] = Field(default_factory=list)
    signals: dict[str, float | int | str] = Field(default_factory=dict)


class RoutingCapabilities(BaseModel):
    vision_available: bool = False


class RouteDecision(BaseModel):
    route: str
    reason: str
    quality_gap: float
    cost_justification: str


class VisionResult(BaseModel):
    text: str
    provider: str
    model: str


class ProcessedInput(BaseModel):
    text: str
    route_taken: str
    metadata: dict[str, float | int | str | list[str]] = Field(default_factory=dict)


class MultimodalProcessingError(RuntimeError):
    def __init__(self, message: str, *, metadata: dict[str, float | int | str | list[str]] | None = None) -> None:
        super().__init__(message)
        self.metadata = dict(metadata) if metadata is not None else None


class OCRExtractor(Protocol):
    def extract(self, file_path: Path) -> OCRResult:
        ...

    @property
    def resolved_command_path(self) -> str:
        ...


class VisionInterpreter(Protocol):
    def interpret(self, file_path: Path, context: ContentExpectation) -> VisionResult:
        ...


class OCRScorer:
    def score(
        self,
        result: OCRResult,
        context: ContentExpectation,
        profile: RoutingProfile,
    ) -> OCRQualityAssessment:
        del profile

        score = result.mean_confidence or 0.0
        reasons: list[str] = []
        stripped_text = result.text.strip()
        words = [word for word in stripped_text.split() if word]
        word_count = len(words)
        symbol_count = sum(1 for char in stripped_text if not char.isalnum() and not char.isspace())
        visible_char_count = sum(1 for char in stripped_text if not char.isspace())
        symbol_density = (symbol_count / visible_char_count) if visible_char_count else 0.0

        if not stripped_text:
            reasons.append("empty_output")
            score = 0.0

        if context is ContentExpectation.UI_TEXT and len(stripped_text) <= 12:
            reasons.append("short_text_allowed_for_ui")
            score = max(score, 0.8)

        document_coverage_insufficient = context is ContentExpectation.DOCUMENT and word_count < 3
        if document_coverage_insufficient:
            reasons.append("insufficient_document_coverage")
            score = max(0.0, score - 0.35)

        if context is ContentExpectation.CODE_IMAGE and symbol_density > 0.2:
            reasons.append("symbol_density_tolerated_for_code")
            score = min(1.0, score + 0.1)

        acceptability = "acceptable"
        if document_coverage_insufficient or score < 0.6:
            acceptability = "poor"

        return OCRQualityAssessment(
            score=score,
            acceptability=acceptability,
            reasons=reasons,
            signals={
                "word_count": word_count,
                "symbol_density": round(symbol_density, 4),
            },
        )


class InputRoutingPolicy:
    def decide_route(
        self,
        context: ContentExpectation,
        assessment: OCRQualityAssessment,
        profile: RoutingProfile,
        capabilities: RoutingCapabilities,
    ) -> RouteDecision:
        del context

        hard_guard_reasons = {"empty_output", "extreme_noise"}
        if any(reason in hard_guard_reasons for reason in assessment.reasons):
            if capabilities.vision_available:
                return RouteDecision(
                    route="escalate_to_vision",
                    reason="ocr_unusable_empty_output" if "empty_output" in assessment.reasons else "ocr_unusable_extreme_noise",
                    quality_gap=max(0.0, round(1.0 - assessment.score, 2)),
                    cost_justification="quality_gap_justifies_escalation",
                )
            return RouteDecision(
                route="fail",
                reason="vision_required_but_unavailable",
                quality_gap=max(0.0, round(1.0 - assessment.score, 2)),
                cost_justification="missing_vision_capability",
            )

        if assessment.acceptability == "acceptable":
            return RouteDecision(
                route="use_ocr",
                reason="acceptable_ocr_lower_cost",
                quality_gap=0.0,
                cost_justification="prefer_lower_cost_path",
            )

        if assessment.acceptability == "borderline":
            if profile is RoutingProfile.ACCURACY_SENSITIVE and capabilities.vision_available:
                return RouteDecision(
                    route="escalate_to_vision",
                    reason="accuracy_priority_overrides_borderline_ocr",
                    quality_gap=max(0.0, round(0.8 - assessment.score, 2)),
                    cost_justification="prefer_accuracy_over_cost",
                )
            return RouteDecision(
                route="use_ocr",
                reason="borderline_ocr_accepted_in_balanced_mode",
                quality_gap=max(0.0, round(0.8 - assessment.score, 2)),
                cost_justification="prefer_ocr_until_quality_gap_is_material",
            )

        if capabilities.vision_available:
            return RouteDecision(
                route="escalate_to_vision",
                reason="poor_ocr_requires_vision",
                quality_gap=max(0.0, round(1.0 - assessment.score, 2)),
                cost_justification="quality_gap_justifies_escalation",
            )

        return RouteDecision(
            route="fail",
            reason="vision_required_but_unavailable",
            quality_gap=max(0.0, round(1.0 - assessment.score, 2)),
            cost_justification="missing_vision_capability",
        )


class MultimodalInputProcessor:
    def __init__(
        self,
        ocr_extractor: OCRExtractor,
        scorer: OCRScorer,
        routing_policy: InputRoutingPolicy,
        vision_interpreter: VisionInterpreter | None = None,
    ) -> None:
        self.ocr_extractor = ocr_extractor
        self.scorer = scorer
        self.routing_policy = routing_policy
        self.vision_interpreter = vision_interpreter

    def process(
        self,
        file_path: str | Path,
        context: ContentExpectation,
        profile: RoutingProfile = RoutingProfile.BALANCED,
    ) -> ProcessedInput:
        path = Path(file_path)
        ocr_result = self.ocr_extractor.extract(path)
        assessment = self.scorer.score(ocr_result, context=context, profile=profile)
        decision = self.routing_policy.decide_route(
            context=context,
            assessment=assessment,
            profile=profile,
            capabilities=RoutingCapabilities(vision_available=self.vision_interpreter is not None),
        )

        metadata: dict[str, float | int | str | list[str]] = {
            "context": context.value,
            "route_taken": decision.route,
            "routing_reason": decision.reason,
            "ocr_score": assessment.score,
            "ocr_acceptability": assessment.acceptability,
            "ocr_reasons": assessment.reasons,
            "cost_justification": decision.cost_justification,
        }
        resolved_command_path = getattr(self.ocr_extractor, "resolved_command_path", None)
        if isinstance(resolved_command_path, str) and resolved_command_path:
            metadata["ocr_binary_path"] = resolved_command_path

        if decision.route == "use_ocr":
            return ProcessedInput(
                text=self._normalize_text(ocr_result.text),
                route_taken=decision.route,
                metadata=metadata,
            )

        if decision.route == "escalate_to_vision":
            if self.vision_interpreter is None:
                raise MultimodalProcessingError(
                    "Vision escalation requested but no vision interpreter is configured.",
                    metadata=metadata,
                )
            vision_result = self.vision_interpreter.interpret(path, context)
            metadata["vision_provider"] = vision_result.provider
            metadata["vision_model"] = vision_result.model
            return ProcessedInput(
                text=self._normalize_text(vision_result.text),
                route_taken=decision.route,
                metadata=metadata,
            )

        raise MultimodalProcessingError(decision.reason, metadata=metadata)

    def _normalize_text(self, text: str) -> str:
        normalized = text.strip()
        if not normalized:
            raise MultimodalProcessingError("Processed multimodal text is empty after normalization.")
        return normalized
