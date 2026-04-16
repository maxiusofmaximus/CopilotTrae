from __future__ import annotations

import csv
import subprocess
import tempfile
import time
from pathlib import Path

from local_ai_agent.multimodal import OCRResult


class OCRExtractionError(RuntimeError):
    pass


class TesseractOCRExtractor:
    def __init__(self, command: str, *, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.command_path = self._resolve_local_command_path(command)
        self.command = str(self.command_path)

    @property
    def resolved_command_path(self) -> str:
        return self.command

    def extract(self, file_path: Path) -> OCRResult:
        start = time.perf_counter()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_base = Path(temp_dir) / "ocr_output"
            command = [self.command, str(file_path), str(output_base), "txt", "tsv"]
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.strip() if exc.stderr else "Unknown Tesseract error."
                raise OCRExtractionError(f"Tesseract OCR failed: {stderr}") from exc

            text = output_base.with_suffix(".txt").read_text(encoding="utf-8")
            mean_confidence, token_confidences = self._parse_tsv_confidence(output_base.with_suffix(".tsv"))
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return OCRResult(
                text=text,
                mean_confidence=mean_confidence,
                token_confidences=token_confidences,
                elapsed_ms=elapsed_ms,
                engine_name="tesseract_cli",
            )

    def _parse_tsv_confidence(self, tsv_path: Path) -> tuple[float | None, list[float]]:
        if not tsv_path.exists():
            return None, []

        confidences: list[float] = []
        with tsv_path.open(encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for row in reader:
                conf = (row.get("conf") or "").strip()
                text = (row.get("text") or "").strip()
                if not conf or not text:
                    continue
                try:
                    numeric_conf = float(conf)
                except ValueError:
                    continue
                if numeric_conf < 0:
                    continue
                confidences.append(round(numeric_conf / 100.0, 2))

        if not confidences:
            return None, []
        return round(sum(confidences) / len(confidences), 2), confidences

    def _resolve_local_command_path(self, command: str) -> Path:
        configured = Path(command)
        candidate = configured if configured.is_absolute() else (self.project_root / configured)
        resolved = candidate.resolve()

        if not self._is_within_project_root(resolved):
            raise OCRExtractionError(
                f"Configured Tesseract binary must be inside the project root: {self.project_root}"
            )
        if not resolved.exists():
            raise OCRExtractionError(f"Configured Tesseract binary does not exist: {resolved}")
        if not resolved.is_file():
            raise OCRExtractionError(f"Configured Tesseract binary is not a file: {resolved}")
        return resolved

    def _is_within_project_root(self, path: Path) -> bool:
        try:
            path.relative_to(self.project_root)
            return True
        except ValueError:
            return False
