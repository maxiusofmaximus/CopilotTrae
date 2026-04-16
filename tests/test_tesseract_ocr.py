import io
import json
import subprocess
from pathlib import Path

import pytest

from local_ai_agent.config import Settings
from local_ai_agent.models import ChatResponse
from local_ai_agent.multimodal import OCRResult


def test_tesseract_ocr_extractor_parses_text_confidence_and_elapsed_time(tmp_path: Path, monkeypatch):
    from local_ai_agent.ocr_extractors import TesseractOCRExtractor

    image_path = tmp_path / "receipt.png"
    image_path.write_bytes(b"fake-image")
    binary_path = tmp_path / "bin" / "tesseract" / "tesseract.exe"
    binary_path.parent.mkdir(parents=True)
    binary_path.write_text("fake-binary", encoding="utf-8")

    def fake_run(command, check, capture_output, text):
        assert command[0] == str(binary_path.resolve())
        assert command[1] == str(image_path)
        output_base = Path(command[2])
        output_base.with_suffix(".txt").write_text("Invoice Total 123.45\n", encoding="utf-8")
        output_base.with_suffix(".tsv").write_text(
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t0\t0\t0\t0\t96\tInvoice\n"
            "5\t1\t1\t1\t1\t2\t0\t0\t0\t0\t84\tTotal\n"
            "5\t1\t1\t1\t1\t3\t0\t0\t0\t0\t90\t123.45\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("local_ai_agent.ocr_extractors.subprocess.run", fake_run)

    extractor = TesseractOCRExtractor(command="bin/tesseract/tesseract.exe", project_root=tmp_path)
    result = extractor.extract(image_path)

    assert isinstance(result, OCRResult)
    assert result.text == "Invoice Total 123.45\n"
    assert result.engine_name == "tesseract_cli"
    assert result.elapsed_ms is not None
    assert result.elapsed_ms >= 0
    assert result.mean_confidence == pytest.approx(0.9, abs=0.01)
    assert result.token_confidences == [0.96, 0.84, 0.9]


def test_tesseract_ocr_extractor_raises_explicit_error_when_binary_is_missing(tmp_path: Path, monkeypatch):
    from local_ai_agent.ocr_extractors import OCRExtractionError, TesseractOCRExtractor

    image_path = tmp_path / "missing.png"
    image_path.write_bytes(b"fake-image")

    with pytest.raises(OCRExtractionError, match="does not exist"):
        TesseractOCRExtractor(command="bin/tesseract/tesseract.exe", project_root=tmp_path)


def test_tesseract_ocr_extractor_rejects_binary_path_outside_project_root(tmp_path: Path):
    from local_ai_agent.ocr_extractors import OCRExtractionError, TesseractOCRExtractor

    outside_binary = tmp_path.parent / "shared-tesseract.exe"
    outside_binary.write_text("fake-binary", encoding="utf-8")

    with pytest.raises(OCRExtractionError, match="inside the project root"):
        TesseractOCRExtractor(command=str(outside_binary), project_root=tmp_path)


def test_runtime_processes_image_file_input_through_multimodal_pipeline_and_logs_metadata(
    tmp_path: Path,
    monkeypatch,
):
    from local_ai_agent.runtime import build_runtime
    from local_ai_agent.session_runner import ReplyRequest

    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"fake-image")

    class FakeProvider:
        provider_name = "fake-provider"

        def complete(self, request):
            return ChatResponse(
                provider="fake-provider",
                model=request.model,
                content="Processed by agent",
                finish_reason="stop",
            )

    class FakeTesseractOCRExtractor:
        def __init__(self, command: str, *, project_root: Path) -> None:
            self.command = command
            self.project_root = project_root

        def extract(self, file_path: Path) -> OCRResult:
            assert file_path == image_path
            return OCRResult(
                text="  Submit order now  ",
                mean_confidence=0.94,
                token_confidences=[0.95, 0.93],
                elapsed_ms=15,
                engine_name="tesseract_cli",
            )

    monkeypatch.setattr("local_ai_agent.runtime.build_provider", lambda settings: FakeProvider())
    monkeypatch.setattr("local_ai_agent.runtime.TesseractOCRExtractor", FakeTesseractOCRExtractor)

    settings = Settings(
        provider="stub",
        model="fake-model",
        api_key="test-key",
        logs_dir=tmp_path,
        session_id="multimodal-session",
    )
    stdout = io.StringIO()
    runtime = build_runtime(settings, stdin=io.StringIO(""), stdout=stdout)

    result = runtime.runner.run_reply(ReplyRequest(text=None, input_file=str(image_path)))

    assert result.exit_code == 0
    assert stdout.getvalue() == "Processed by agent\n"

    log_path = tmp_path / "multimodal-session.jsonl"
    entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["request"]["input"] == "Submit order now"
    assert entry["input_metadata"]["route_taken"] == "use_ocr"
    assert entry["input_metadata"]["routing_reason"] == "acceptable_ocr_lower_cost"
    assert entry["input_metadata"]["ocr_score"] == 0.94
    assert entry["input_metadata"]["context"] == "document"


def test_runtime_logs_multimodal_fail_path_metadata_before_agent_call(tmp_path: Path, monkeypatch):
    from local_ai_agent.multimodal import MultimodalProcessingError
    from local_ai_agent.runtime import build_runtime
    from local_ai_agent.session_runner import ReplyRequest

    image_path = tmp_path / "noisy_scan_heavy.png"
    image_path.write_bytes(b"fake-image")

    class FakeProvider:
        provider_name = "fake-provider"

        def complete(self, request):
            raise AssertionError("Agent provider should not run when preprocessing fails.")

    class FakeTesseractOCRExtractor:
        def __init__(self, command: str, *, project_root: Path) -> None:
            self.command = command
            self.project_root = project_root

        def extract(self, file_path: Path) -> OCRResult:
            assert file_path == image_path
            return OCRResult(
                text="   ",
                mean_confidence=0.02,
                token_confidences=[],
                elapsed_ms=21,
                engine_name="tesseract_cli",
            )

    monkeypatch.setattr("local_ai_agent.runtime.build_provider", lambda settings: FakeProvider())
    monkeypatch.setattr("local_ai_agent.runtime.TesseractOCRExtractor", FakeTesseractOCRExtractor)

    settings = Settings(
        provider="stub",
        model="fake-model",
        api_key="test-key",
        logs_dir=tmp_path,
        session_id="multimodal-fail-session",
    )
    runtime = build_runtime(settings, stdin=io.StringIO(""), stdout=io.StringIO())

    with pytest.raises(MultimodalProcessingError, match="vision_required_but_unavailable"):
        runtime.runner.run_reply(ReplyRequest(text=None, input_file=str(image_path)))

    log_path = tmp_path / "multimodal-fail-session.jsonl"
    entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["event"] == "input_processing_failure"
    assert entry["error"]["type"] == "MultimodalProcessingError"
    assert entry["error"]["message"] == "vision_required_but_unavailable"
    assert entry["request"]["input_file"] == str(image_path)
    assert entry["input_metadata"]["route_taken"] == "fail"
    assert entry["input_metadata"]["routing_reason"] == "vision_required_but_unavailable"
    assert entry["input_metadata"]["ocr_score"] == 0.0
