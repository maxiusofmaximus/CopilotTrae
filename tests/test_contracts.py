import io
from typing import Any

from local_ai_agent.input_adapters import FileInputSource, PromptedLineInputSource, StreamInputSource
from local_ai_agent.logging_utils import InteractionLogger
from local_ai_agent.memory import ConversationMemory
from local_ai_agent.output_adapters import ConsoleOutputSink, StreamConfirmationPolicy, TkClipboardSink


def test_memory_and_logger_satisfy_runtime_contracts(tmp_path):
    from local_ai_agent.contracts import InteractionLogSink, MemoryStore

    memory = ConversationMemory(max_messages=2, system_prompt="System prompt")
    logger = InteractionLogger(logs_dir=tmp_path, session_id="session")

    assert isinstance(memory, MemoryStore)
    assert isinstance(logger, InteractionLogSink)


def test_memory_store_and_log_sink_are_independently_usable(tmp_path):
    from local_ai_agent.contracts import InteractionLogSink, MemoryStore

    memory: MemoryStore = ConversationMemory(max_messages=2, system_prompt="System prompt")
    logger: InteractionLogSink = InteractionLogger(logs_dir=tmp_path, session_id="session")

    messages = memory.build_request_messages("Hello")
    log_path = logger.log_interaction({"request": {"input": "Hello"}})

    assert messages[0].role == "system"
    assert log_path.exists()


def test_runtime_io_implementations_satisfy_contracts(tmp_path):
    from local_ai_agent.contracts import ClipboardSink, ConfirmationPolicy, InputSource, OutputSink

    input_file = tmp_path / "input.txt"
    input_file.write_text("Hello", encoding="utf-8")

    manual = PromptedLineInputSource(io.StringIO("Hello\n"))
    stdin = StreamInputSource(io.StringIO("Hello"))
    file_input = FileInputSource(input_file)
    output = ConsoleOutputSink(io.StringIO())
    confirmer = StreamConfirmationPolicy(io.StringIO("y\n"), output)
    clipboard = TkClipboardSink()

    assert isinstance(manual, InputSource)
    assert isinstance(stdin, InputSource)
    assert isinstance(file_input, InputSource)
    assert isinstance(output, OutputSink)
    assert isinstance(confirmer, ConfirmationPolicy)
    assert isinstance(clipboard, ClipboardSink)
