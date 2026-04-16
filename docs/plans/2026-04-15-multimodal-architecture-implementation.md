# Multimodal Architecture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add deterministic multimodal preprocessing with OCR-first routing, quality scoring, and an optional vision escalation seam without changing `AgentController`, `LLMClient`, or `ChatRequest`.

**Architecture:** Introduce a pre-agent multimodal layer that accepts file paths, runs OCR first, scores OCR quality using deterministic context-aware heuristics, and decides whether to accept OCR text, escalate to an optional `VisionInterpreter`, or fail. Keep routing and orchestration entirely inside `MultimodalInputProcessor`, and return normalized text plus structured metadata so the existing agent pipeline remains unchanged.

**Tech Stack:** Python 3.12, `pydantic`, `pytest`, existing runtime/session/input abstractions

---

### Task 1: Add Red Tests For OCR Scoring

**Files:**
- Create: `tests/test_multimodal_scoring.py`
- Create: `src/local_ai_agent/multimodal.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_multimodal_scoring.py::test_ocr_scorer_accepts_short_high_confidence_ui_text -v`
Expected: FAIL because `local_ai_agent.multimodal` does not exist

**Step 3: Write minimal implementation**

```python
class OCRScorer:
    def score(self, result: OCRResult, context: ContentExpectation, profile: RoutingProfile) -> OCRQualityAssessment:
        score = result.mean_confidence or 0.0
        reasons = []
        if context is ContentExpectation.UI_TEXT and len(result.text.strip()) <= 12:
            reasons.append("short_text_allowed_for_ui")
            score = max(score, 0.8)
        return OCRQualityAssessment(score=score, acceptability="acceptable", reasons=reasons, signals={})
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_multimodal_scoring.py::test_ocr_scorer_accepts_short_high_confidence_ui_text -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_multimodal_scoring.py src/local_ai_agent/multimodal.py
git commit -m "feat: add deterministic ocr scoring foundation"
```

### Task 2: Expand OCR Scoring With Context-Aware Heuristics

**Files:**
- Modify: `tests/test_multimodal_scoring.py`
- Modify: `src/local_ai_agent/multimodal.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_multimodal_scoring.py -v`
Expected: FAIL because document and code-specific heuristics are not implemented

**Step 3: Write minimal implementation**

```python
if context is ContentExpectation.DOCUMENT and word_count < 3:
    penalties.append(0.35)
    reasons.append("insufficient_document_coverage")

if context is ContentExpectation.CODE_IMAGE and symbol_density > 0.2:
    bonuses.append(0.1)
    reasons.append("symbol_density_tolerated_for_code")
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_multimodal_scoring.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_multimodal_scoring.py src/local_ai_agent/multimodal.py
git commit -m "feat: add context-aware ocr scoring heuristics"
```

### Task 3: Add Deterministic Routing Policy

**Files:**
- Create: `tests/test_multimodal_routing.py`
- Modify: `src/local_ai_agent/multimodal.py`

**Step 1: Write the failing tests**

```python
from local_ai_agent.multimodal import (
    ContentExpectation,
    OCRQualityAssessment,
    InputRoutingPolicy,
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
            signals={"word_count": 42},
        ),
        profile=RoutingProfile.COST_SENSITIVE,
        capabilities=RoutingCapabilities(vision_available=True),
    )

    assert decision.route == "use_ocr"
    assert decision.reason == "acceptable_ocr_lower_cost"


def test_routing_policy_escalates_borderline_ocr_in_accuracy_sensitive_mode():
    policy = InputRoutingPolicy()

    decision = policy.decide_route(
        context=ContentExpectation.DOCUMENT,
        assessment=OCRQualityAssessment(
            score=0.72,
            acceptability="borderline",
            reasons=["borderline_document_quality"],
            signals={"word_count": 42},
        ),
        profile=RoutingProfile.ACCURACY_SENSITIVE,
        capabilities=RoutingCapabilities(vision_available=True),
    )

    assert decision.route == "use_vision"
    assert decision.reason == "accuracy_priority_overrides_borderline_ocr"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_multimodal_routing.py -v`
Expected: FAIL because `InputRoutingPolicy` and routing models do not exist

**Step 3: Write minimal implementation**

```python
class InputRoutingPolicy:
    def decide_route(...):
        if assessment.acceptability == "acceptable":
            return RouteDecision(route="use_ocr", reason="acceptable_ocr_lower_cost", quality_gap=0.0, cost_justification="prefer_ocr")
        if profile is RoutingProfile.ACCURACY_SENSITIVE and capabilities.vision_available:
            return RouteDecision(route="use_vision", reason="accuracy_priority_overrides_borderline_ocr", quality_gap=0.08, cost_justification="prefer_accuracy")
        ...
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_multimodal_routing.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_multimodal_routing.py src/local_ai_agent/multimodal.py
git commit -m "feat: add deterministic multimodal routing policy"
```

### Task 4: Cover Hard Guards And Missing Vision Capability

**Files:**
- Modify: `tests/test_multimodal_routing.py`
- Modify: `src/local_ai_agent/multimodal.py`

**Step 1: Write the failing tests**

```python
def test_routing_policy_escalates_empty_ocr_output_when_vision_is_available():
    policy = InputRoutingPolicy()

    decision = policy.decide_route(
        context=ContentExpectation.DOCUMENT,
        assessment=OCRQualityAssessment(
            score=0.05,
            acceptability="poor",
            reasons=["empty_output"],
            signals={"word_count": 0},
        ),
        profile=RoutingProfile.BALANCED,
        capabilities=RoutingCapabilities(vision_available=True),
    )

    assert decision.route == "use_vision"
    assert decision.reason == "ocr_unusable"


def test_routing_policy_fails_when_vision_is_required_but_unavailable():
    policy = InputRoutingPolicy()

    decision = policy.decide_route(
        context=ContentExpectation.DIAGRAM,
        assessment=OCRQualityAssessment(
            score=0.18,
            acceptability="poor",
            reasons=["diagram_requires_visual_interpretation"],
            signals={"word_count": 1},
        ),
        profile=RoutingProfile.BALANCED,
        capabilities=RoutingCapabilities(vision_available=False),
    )

    assert decision.route == "fail"
    assert decision.reason == "vision_required_but_unavailable"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_multimodal_routing.py -v`
Expected: FAIL because hard-guard routing and failure behavior are not implemented

**Step 3: Write minimal implementation**

```python
if "empty_output" in assessment.reasons and capabilities.vision_available:
    return RouteDecision(route="use_vision", reason="ocr_unusable", quality_gap=1.0, cost_justification="quality_gap_justifies_escalation")
if assessment.acceptability == "poor" and not capabilities.vision_available:
    return RouteDecision(route="fail", reason="vision_required_but_unavailable", quality_gap=1.0, cost_justification="missing_capability")
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_multimodal_routing.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_multimodal_routing.py src/local_ai_agent/multimodal.py
git commit -m "feat: add multimodal routing hard guards"
```

### Task 5: Add Processor Integration And Vision Extension Seam

**Files:**
- Create: `tests/test_multimodal_processor.py`
- Modify: `src/local_ai_agent/multimodal.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

from local_ai_agent.multimodal import (
    ContentExpectation,
    MultimodalInputProcessor,
    OCRResult,
    ProcessedInput,
    RouteDecision,
    VisionResult,
)


def test_processor_uses_ocr_text_when_routing_accepts_it(tmp_path: Path):
    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"fake")

    class FakeOCR:
        def extract(self, file_path):
            return OCRResult(text="Save", mean_confidence=0.97, token_confidences=[0.97], elapsed_ms=10)

    class FakeScorer:
        def score(self, result, context, profile):
            return OCRQualityAssessment(score=0.9, acceptability="acceptable", reasons=["ui_quality_pass"], signals={})

    class FakePolicy:
        def decide_route(self, context, assessment, profile, capabilities):
            return RouteDecision(route="use_ocr", reason="acceptable_ocr_lower_cost", quality_gap=0.0, cost_justification="prefer_ocr")

    processor = MultimodalInputProcessor(
        ocr_extractor=FakeOCR(),
        scorer=FakeScorer(),
        routing_policy=FakePolicy(),
        vision_interpreter=None,
    )

    processed = processor.process(image_path, context=ContentExpectation.UI_TEXT)

    assert isinstance(processed, ProcessedInput)
    assert processed.text == "Save"
    assert processed.route_taken == "use_ocr"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_multimodal_processor.py -v`
Expected: FAIL because `MultimodalInputProcessor`, `ProcessedInput`, and `VisionInterpreter` seam do not exist

**Step 3: Write minimal implementation**

```python
class VisionInterpreter(Protocol):
    def interpret(self, file_path: Path, context: ContentExpectation) -> VisionResult:
        ...


class MultimodalInputProcessor:
    def process(self, file_path: str | Path, context: ContentExpectation, profile: RoutingProfile = RoutingProfile.BALANCED) -> ProcessedInput:
        ocr_result = self.ocr_extractor.extract(Path(file_path))
        assessment = self.scorer.score(ocr_result, context=context, profile=profile)
        decision = self.routing_policy.decide_route(
            context=context,
            assessment=assessment,
            profile=profile,
            capabilities=RoutingCapabilities(vision_available=self.vision_interpreter is not None),
        )
        if decision.route == "use_ocr":
            return ProcessedInput(text=ocr_result.text.strip(), route_taken=decision.route, metadata={...})
        ...
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_multimodal_processor.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_multimodal_processor.py src/local_ai_agent/multimodal.py
git commit -m "feat: add multimodal processor orchestration seam"
```

### Task 6: Cover Vision Escalation And Structured Observability

**Files:**
- Modify: `tests/test_multimodal_processor.py`
- Modify: `src/local_ai_agent/multimodal.py`

**Step 1: Write the failing tests**

```python
def test_processor_calls_vision_only_after_ocr_escalation(tmp_path: Path):
    image_path = tmp_path / "diagram.png"
    image_path.write_bytes(b"fake")
    calls = {"vision": 0}

    class FakeOCR:
        def extract(self, file_path):
            return OCRResult(text="", mean_confidence=0.1, token_confidences=[0.1], elapsed_ms=12)

    class FakeScorer:
        def score(self, result, context, profile):
            return OCRQualityAssessment(score=0.1, acceptability="poor", reasons=["empty_output"], signals={"word_count": 0})

    class FakePolicy:
        def decide_route(self, context, assessment, profile, capabilities):
            return RouteDecision(route="use_vision", reason="ocr_unusable", quality_gap=1.0, cost_justification="quality_gap_justifies_escalation")

    class FakeVision:
        def interpret(self, file_path, context):
            calls["vision"] += 1
            return VisionResult(text="A diagram showing a payment workflow.", provider="fake-vision", model="vision-model")

    processor = MultimodalInputProcessor(
        ocr_extractor=FakeOCR(),
        scorer=FakeScorer(),
        routing_policy=FakePolicy(),
        vision_interpreter=FakeVision(),
    )

    processed = processor.process(image_path, context=ContentExpectation.DIAGRAM)

    assert processed.text == "A diagram showing a payment workflow."
    assert processed.route_taken == "use_vision"
    assert processed.metadata["routing_reason"] == "ocr_unusable"
    assert calls["vision"] == 1
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_multimodal_processor.py -v`
Expected: FAIL because vision escalation and metadata capture are incomplete

**Step 3: Write minimal implementation**

```python
if decision.route == "use_vision":
    if self.vision_interpreter is None:
        raise ValueError("Vision interpreter is required for vision escalation.")
    vision_result = self.vision_interpreter.interpret(path, context)
    return ProcessedInput(
        text=vision_result.text.strip(),
        route_taken=decision.route,
        metadata={
            "routing_reason": decision.reason,
            "cost_justification": decision.cost_justification,
            "ocr_score": assessment.score,
            "ocr_reasons": assessment.reasons,
            "vision_provider": vision_result.provider,
            "vision_model": vision_result.model,
        },
    )
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_multimodal_processor.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_multimodal_processor.py src/local_ai_agent/multimodal.py
git commit -m "feat: add multimodal vision escalation path"
```

### Task 7: Verify Deterministic Multimodal Behavior

**Files:**
- Test: `tests/test_multimodal_scoring.py`
- Test: `tests/test_multimodal_routing.py`
- Test: `tests/test_multimodal_processor.py`
- Diagnostics: touched source and test files

**Step 1: Run focused multimodal tests**

Run: `python -m pytest tests/test_multimodal_scoring.py tests/test_multimodal_routing.py tests/test_multimodal_processor.py -v`
Expected: PASS

**Step 2: Run the full test suite**

Run: `python -m pytest -v`
Expected: PASS

**Step 3: Run diagnostics**

Use editor diagnostics on:
- `src/local_ai_agent/multimodal.py`
- `tests/test_multimodal_scoring.py`
- `tests/test_multimodal_routing.py`
- `tests/test_multimodal_processor.py`

Expected: no new errors

**Step 4: Commit**

```bash
git add src/local_ai_agent/multimodal.py tests/test_multimodal_scoring.py tests/test_multimodal_routing.py tests/test_multimodal_processor.py
git commit -m "test: validate deterministic multimodal routing core"
```

### Task 8: Integrate Real OCR And Vision Only After Green Deterministic Tests

**Files:**
- Modify later after deterministic core is green

**Step 1: Add a real OCR engine adapter behind the `ocr_extractor` seam**

```python
class TesseractOCRExtractor:
    def extract(self, file_path: Path) -> OCRResult:
        ...
```

**Step 2: Add a real `VisionInterpreter` adapter for a vision-capable provider**

```python
class GLMVisionInterpreter:
    def interpret(self, file_path: Path, context: ContentExpectation) -> VisionResult:
        ...
```

**Step 3: Run deterministic tests before any live tests**

Run: `python -m pytest tests/test_multimodal_scoring.py tests/test_multimodal_routing.py tests/test_multimodal_processor.py -v`
Expected: PASS

**Step 4: Add live validation only after deterministic core remains green**

Run live validation after provider-specific adapters are added.
