from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from typing import TextIO

from local_ai_agent.agent import AgentController
from local_ai_agent.config import Settings
from local_ai_agent.contracts import MemoryStore, OutputSink, RouterEventSink
from local_ai_agent.input_adapters import MultimodalFileInputSource, PromptedLineInputSource, StreamInputSource
from local_ai_agent.logging_utils import InteractionLogger
from local_ai_agent.memory import ConversationMemory, PersistentConversationMemory
from local_ai_agent.modules.registry import ModuleRegistry
from local_ai_agent.modules.snapshot_builder import build_registry_snapshot
from local_ai_agent.multimodal import InputRoutingPolicy, MultimodalInputProcessor, OCRScorer
from local_ai_agent.ocr_extractors import TesseractOCRExtractor
from local_ai_agent.output_adapters import ConsoleOutputSink, StreamConfirmationPolicy, TkClipboardSink
from local_ai_agent.providers import build_provider
from local_ai_agent.router.pipeline import DeterministicRouter
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
from local_ai_agent.router.runtime_services import CachedSnapshotProvider, JsonlRouterEventSink, SnapshotProvider
from local_ai_agent.router.snapshot import RegistrySnapshot
from local_ai_agent.session_runner import AgentSessionRunner, serialize_router_envelope
from local_ai_agent.tools.adapters.generic_cli import GenericCliToolAdapter
from local_ai_agent.tools.registry import ToolRegistry

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
WINDOWS_EXECUTABLE_SUFFIXES = frozenset(suffix.lower() for suffix in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(os.pathsep))
KNOWN_TOOL_ALIASES: dict[str, tuple[str, ...]] = {
    "gh": ("github-cli",),
    "pwsh": ("powershell", "powershell7"),
    "python": ("python3",),
}


@dataclass(slots=True)
class AppRuntime:
    runner: AgentSessionRunner
    output: OutputSink
    router_runtime: object | None = None


@dataclass(slots=True)
class RouterRuntime:
    router: object
    snapshot_provider: SnapshotProvider
    event_sink: RouterEventSink
    default_session_id: str

    @property
    def snapshot(self) -> RegistrySnapshot:
        return self.snapshot_provider.get_snapshot(self.default_session_id)

    def resolve(self, request: TerminalRequest) -> RouteEnvelope | RouterErrorEnvelope:
        snapshot = self.snapshot_provider.get_snapshot(request.session_id)
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
                snapshot_version=snapshot.snapshot_version,
            )
        )
        result = self.router.resolve(request, snapshot)
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


class NullRouterEventSink:
    def emit(self, event: object) -> None:
        del event


def build_router_runtime(
    settings: Settings,
    *,
    shell: str,
) -> RouterRuntime:
    tool_registry = ToolRegistry()
    for tool_name, binary_path in _iter_path_tools():
        tool_registry.register(
            tool_name=tool_name,
            adapter=GenericCliToolAdapter(shell=shell),
            binary_path=binary_path,
            aliases=list(KNOWN_TOOL_ALIASES.get(tool_name, ())),
            capabilities=[],
            available=True,
        )
    module_registry = ModuleRegistry()
    snapshot_provider = CachedSnapshotProvider(
        snapshot_factory=lambda session_id: build_registry_snapshot(
            session_id=session_id,
            tool_registry=tool_registry,
            module_registry=module_registry,
        )
    )
    return RouterRuntime(
        router=DeterministicRouter(),
        snapshot_provider=snapshot_provider,
        event_sink=JsonlRouterEventSink(settings.logs_dir / "router" / f"{settings.session_id}.jsonl"),
        default_session_id=settings.session_id,
    )


def _iter_path_tools() -> Iterable[tuple[str, Path]]:
    seen: set[str] = set()
    for raw_directory in os.environ.get("PATH", "").split(os.pathsep):
        if not raw_directory:
            continue
        directory = Path(raw_directory)
        if not directory.is_dir():
            continue
        try:
            children = directory.iterdir()
        except OSError:
            continue
        for child in children:
            if not child.is_file():
                continue
            tool_name = _tool_name_from_path(child)
            if tool_name is None or tool_name in seen:
                continue
            seen.add(tool_name)
            yield tool_name, child


def _tool_name_from_path(path: Path) -> str | None:
    if os.name == "nt":
        if path.suffix.lower() not in WINDOWS_EXECUTABLE_SUFFIXES:
            return None
        return path.stem.lower()
    if os.access(path, os.X_OK):
        return path.name.lower()
    return None


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
    router_runtime = build_router_runtime(settings, shell=_default_router_shell())
    return AppRuntime(runner=runner, output=output, router_runtime=router_runtime)


def _default_router_shell() -> str:
    if os.name == "nt":
        return "powershell"
    return "bash"
