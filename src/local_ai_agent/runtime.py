from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from local_ai_agent.agent import AgentController
from local_ai_agent.config import Settings
from local_ai_agent.contracts import MemoryStore, OutputSink, RouterEventSink
from local_ai_agent.input_adapters import MultimodalFileInputSource, PromptedLineInputSource, StreamInputSource
from local_ai_agent.logging_utils import InteractionLogger
from local_ai_agent.memory import ConversationMemory, PersistentConversationMemory
from local_ai_agent.multimodal import InputRoutingPolicy, MultimodalInputProcessor, OCRScorer
from local_ai_agent.ocr_extractors import TesseractOCRExtractor
from local_ai_agent.output_adapters import ConsoleOutputSink, StreamConfirmationPolicy, TkClipboardSink
from local_ai_agent.providers import build_provider
from local_ai_agent.router.errors import RouterErrorEnvelope
from local_ai_agent.router.events import (
    RouterErrorEmitted,
    RouterIntentClassified,
    RouterRequestReceived,
    RouterRouteEmitted,
    RouterSnapshotBound,
)
from local_ai_agent.router.output import RouteEnvelope
from local_ai_agent.router.request import TerminalRequest
from local_ai_agent.router.snapshot import RegistrySnapshot
from local_ai_agent.session_runner import AgentSessionRunner, serialize_router_envelope

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class AppRuntime:
    runner: AgentSessionRunner
    output: OutputSink
    router_runtime: object | None = None


@dataclass(slots=True)
class RouterRuntime:
    router: object
    snapshot: RegistrySnapshot
    event_sink: RouterEventSink

    def resolve(self, request: TerminalRequest) -> RouteEnvelope | RouterErrorEnvelope:
        self.event_sink.emit(
            RouterRequestReceived(
                request_id=request.request_id,
                session_id=request.session_id,
                request_snapshot_version=request.snapshot_version,
                shell=request.shell,
                raw_input=request.raw_input,
            )
        )
        self.event_sink.emit(
            RouterSnapshotBound(
                request_id=request.request_id,
                session_id=request.session_id,
                snapshot_version=self.snapshot.snapshot_version,
            )
        )
        result = self.router.resolve(request, self.snapshot)
        if isinstance(result, RouterErrorEnvelope):
            self.event_sink.emit(
                RouterErrorEmitted(
                    request_id=request.request_id,
                    session_id=request.session_id,
                    snapshot_version=result.snapshot_version,
                    error_code=result.error_code,
                    diagnostics=dict(result.diagnostics),
                )
            )
            return result

        self.event_sink.emit(
            RouterIntentClassified(
                request_id=request.request_id,
                session_id=request.session_id,
                snapshot_version=result.snapshot_version,
                intent=result.intent,
            )
        )
        self.event_sink.emit(
            RouterRouteEmitted(
                request_id=request.request_id,
                session_id=request.session_id,
                snapshot_version=result.snapshot_version,
                route=result.route,
                intent=result.intent,
            )
        )
        return result

    def resolve_serialized(self, request: TerminalRequest) -> dict[str, object]:
        return serialize_router_envelope(self.resolve(request))


def build_memory_store(settings: Settings) -> MemoryStore:
    if settings.persistent_memory_enabled:
        return PersistentConversationMemory(
            max_messages=settings.max_memory_messages,
            system_prompt=settings.system_prompt,
            storage_path=settings.memory_dir / f"{settings.session_id}.jsonl",
        )
    return ConversationMemory(
        max_messages=settings.max_memory_messages,
        system_prompt=settings.system_prompt,
    )


def build_multimodal_input_processor(
    settings: Settings,
    *,
    project_root: Path = PROJECT_ROOT,
) -> MultimodalInputProcessor:
    ocr_extractor = TesseractOCRExtractor(
        command=settings.tesseract_command,
        project_root=project_root,
    )
    LOGGER.info("Resolved OCR binary path: %s", ocr_extractor.command)
    return MultimodalInputProcessor(
        ocr_extractor=ocr_extractor,
        scorer=OCRScorer(),
        routing_policy=InputRoutingPolicy(),
        vision_interpreter=None,
    )


def build_runtime(settings: Settings, stdin: TextIO, stdout: TextIO) -> AppRuntime:
    memory = build_memory_store(settings)
    provider = build_provider(settings)
    logger = InteractionLogger(logs_dir=settings.logs_dir, session_id=settings.session_id)
    agent = AgentController(settings=settings, llm_client=provider, memory=memory, logger=logger)
    output = ConsoleOutputSink(stdout)
    confirmer = StreamConfirmationPolicy(stdin, output) if settings.confirm_before_copy else None
    reply_input = StreamInputSource(stdin) if not stdin.isatty() else PromptedLineInputSource(stdin, prompt="Message: ", prompt_stream=stdout)
    chat_input = PromptedLineInputSource(stdin)
    multimodal_processor = build_multimodal_input_processor(settings)
    runner = AgentSessionRunner(
        agent=agent,
        output=output,
        clipboard=TkClipboardSink(),
        confirmer=confirmer,
        input_source=reply_input,
        chat_input_source=chat_input,
        file_source_factory=lambda path: MultimodalFileInputSource(path, processor=multimodal_processor),
    )
    return AppRuntime(runner=runner, output=output)
