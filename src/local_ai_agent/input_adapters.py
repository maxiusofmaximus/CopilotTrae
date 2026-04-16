from __future__ import annotations

from pathlib import Path
from typing import TextIO

from local_ai_agent.contracts import InputSource
from local_ai_agent.multimodal import ContentExpectation, MultimodalInputProcessor, MultimodalProcessingError, RoutingProfile


class PromptedLineInputSource(InputSource):
    def __init__(self, stream: TextIO, prompt: str | None = None, prompt_stream: TextIO | None = None) -> None:
        self.stream = stream
        self.prompt = prompt
        self.prompt_stream = prompt_stream

    def read(self) -> str:
        if self.prompt and self.prompt_stream is not None:
            self.prompt_stream.write(self.prompt)
            self.prompt_stream.flush()
        return self.stream.readline()


class StreamInputSource(InputSource):
    def __init__(self, stream: TextIO) -> None:
        self.stream = stream

    def read(self) -> str:
        return self.stream.read()


class FileInputSource(InputSource):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def read(self) -> str:
        return self.path.read_text(encoding="utf-8")


class MultimodalFileInputSource(InputSource):
    IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif"}

    def __init__(
        self,
        path: str | Path,
        processor: MultimodalInputProcessor,
        *,
        default_context: ContentExpectation = ContentExpectation.DOCUMENT,
        routing_profile: RoutingProfile = RoutingProfile.BALANCED,
    ) -> None:
        self.path = Path(path)
        self.processor = processor
        self.default_context = default_context
        self.routing_profile = routing_profile
        self.last_metadata: dict[str, float | int | str | list[str]] | None = None

    def read(self) -> str:
        if self.path.suffix.lower() not in self.IMAGE_SUFFIXES:
            self.last_metadata = None
            return self.path.read_text(encoding="utf-8")

        try:
            processed = self.processor.process(
                self.path,
                context=self.default_context,
                profile=self.routing_profile,
            )
        except MultimodalProcessingError as exc:
            self.last_metadata = dict(exc.metadata) if exc.metadata is not None else None
            raise
        self.last_metadata = processed.metadata
        return processed.text
