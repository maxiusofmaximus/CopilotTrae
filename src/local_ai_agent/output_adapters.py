from __future__ import annotations

import tkinter
from typing import TextIO

from local_ai_agent.contracts import ClipboardSink, ConfirmationPolicy, OutputSink


class ConsoleOutputSink(OutputSink):
    def __init__(self, stream: TextIO) -> None:
        self.stream = stream

    def emit(self, text: str) -> None:
        self.stream.write(text + "\n")
        self.stream.flush()


class StreamConfirmationPolicy(ConfirmationPolicy):
    def __init__(self, stream: TextIO, output: OutputSink) -> None:
        self.stream = stream
        self.output = output

    def confirm(self, prompt: str) -> bool:
        self.output.emit(f"{prompt} [y/N]")
        return self.stream.readline().strip().lower() in {"y", "yes"}


class TkClipboardSink(ClipboardSink):
    def copy(self, text: str) -> None:
        root = tkinter.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        root.destroy()
