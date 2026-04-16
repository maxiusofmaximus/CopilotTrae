from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from local_ai_agent.contracts import ClipboardSink, ConfirmationPolicy, InputSource, OutputSink
from local_ai_agent.multimodal import MultimodalProcessingError
from local_ai_agent.router.errors import RouterErrorEnvelope
from local_ai_agent.router.output import RouteEnvelope


@dataclass(slots=True)
class ReplyRequest:
    text: str | None
    input_source: InputSource | None = None
    input_file: str | None = None
    copy_response: bool = False
    show_memory: bool = False


@dataclass(slots=True)
class SessionResult:
    exit_code: int
    log_path: Path | None = None


def serialize_router_envelope(envelope: RouteEnvelope | RouterErrorEnvelope) -> dict[str, object]:
    if isinstance(envelope, RouterErrorEnvelope):
        return {
            "kind": envelope.kind,
            "snapshot_version": envelope.snapshot_version,
            "error_code": envelope.error_code,
            "request_id": envelope.request_id,
            "session_id": envelope.session_id,
            "diagnostics": dict(envelope.diagnostics),
        }

    return {
        "kind": envelope.kind,
        "snapshot_version": envelope.snapshot_version,
        "route": envelope.route,
        "intent": envelope.intent,
        "payload": envelope.payload,
        "evidence": envelope.evidence,
        "confidence": envelope.confidence,
        "threshold_applied": envelope.threshold_applied,
        "threshold_source": envelope.threshold_source,
        "resolver_path": envelope.resolver_path,
    }


class AgentSessionRunner:
    def __init__(
        self,
        agent,
        output: OutputSink,
        clipboard: ClipboardSink | None = None,
        confirmer: ConfirmationPolicy | None = None,
        input_source: InputSource | None = None,
        chat_input_source: InputSource | None = None,
        file_source_factory: Callable[[str], InputSource] | None = None,
    ) -> None:
        self.agent = agent
        self.output = output
        self.clipboard = clipboard
        self.confirmer = confirmer
        self.input_source = input_source
        self.chat_input_source = chat_input_source or input_source
        self.file_source_factory = file_source_factory
        self._last_input_metadata: dict[str, object] | None = None

    def run_reply(self, request: ReplyRequest) -> SessionResult:
        try:
            raw_text = self._resolve_reply_text(request)
        except MultimodalProcessingError as exc:
            self._log_input_processing_failure(request, exc)
            raise

        result = self.agent.run_once(raw_text)
        self._append_input_metadata_to_log(result.log_path)
        self.output.emit(result.response_text)

        if request.copy_response:
            self._maybe_copy(result.response_text)

        if request.show_memory:
            self._emit_memory(result.memory_snapshot)

        return SessionResult(exit_code=0, log_path=result.log_path)

    def run_chat(self, *, show_memory: bool, copy_response: bool = False) -> int:
        if self.chat_input_source is None:
            raise ValueError("A chat input source is required for chat sessions.")

        self.output.emit("Interactive session started. Type /exit to quit.")
        while True:
            raw_text = self.chat_input_source.read()
            if not raw_text:
                return 0
            if raw_text.strip() in {"/exit", "/quit"}:
                self.output.emit("Session closed.")
                return 0

            result = self.agent.run_once(raw_text)
            self.output.emit(f"Agent> {result.response_text}")
            if copy_response:
                self._maybe_copy(result.response_text)
            if show_memory:
                self._emit_memory(result.memory_snapshot)

    def _resolve_reply_text(self, request: ReplyRequest) -> str:
        self._last_input_metadata = None
        if request.text is not None:
            return request.text
        if request.input_source is not None:
            return self._read_from_source(request.input_source)
        if request.input_file is not None:
            if self.file_source_factory is None:
                raise ValueError("A file input factory is required for file-based replies.")
            return self._read_from_source(self.file_source_factory(request.input_file))
        if self.input_source is not None:
            return self._read_from_source(self.input_source)
        raise ValueError("An input source is required when inline text is not provided.")

    def _read_from_source(self, source: InputSource) -> str:
        text = source.read()
        metadata = getattr(source, "last_metadata", None)
        self._last_input_metadata = dict(metadata) if isinstance(metadata, dict) else None
        return text

    def _log_input_processing_failure(self, request: ReplyRequest, exc: MultimodalProcessingError) -> None:
        # Fail-path logging must happen even when preprocessing prevents agent execution.
        logger = getattr(self.agent, "logger", None)
        if logger is None or not hasattr(logger, "log_interaction"):
            return

        payload: dict[str, object] = {
            "event": "input_processing_failure",
            "error": {"type": type(exc).__name__, "message": str(exc)},
            "request": {
                "text": request.text,
                "input_file": request.input_file,
            },
        }
        if exc.metadata is not None:
            payload["input_metadata"] = exc.metadata

        logger.log_interaction(payload)

    def _append_input_metadata_to_log(self, log_path: Path | None) -> None:
        if self._last_input_metadata is None or log_path is None or not log_path.exists():
            return

        lines = log_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return

        entry = json.loads(lines[-1])
        entry["input_metadata"] = self._last_input_metadata
        lines[-1] = json.dumps(entry, ensure_ascii=True)
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _maybe_copy(self, response_text: str) -> None:
        if self.clipboard is None:
            self.output.emit("Clipboard adapter is unavailable.")
            return

        should_copy = True
        if self.confirmer is not None:
            should_copy = self.confirmer.confirm("Copy response to clipboard?")

        if should_copy:
            self.clipboard.copy(response_text)
            self.output.emit("Response copied to clipboard.")
        else:
            self.output.emit("Clipboard copy skipped.")

    def _emit_memory(self, messages) -> None:
        self.output.emit("Memory:")
        for message in messages:
            self.output.emit(f"- {message.role}: {message.content}")
