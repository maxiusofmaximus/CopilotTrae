import io

from local_ai_agent.cli import main


class FakeRunner:
    def __init__(self) -> None:
        self.reply_calls: list[object] = []
        self.chat_calls: list[dict[str, bool]] = []

    def run_reply(self, request):
        self.reply_calls.append(request)
        return type("SessionResult", (), {"exit_code": 0})()

    def run_chat(self, *, show_memory: bool, copy_response: bool = False) -> int:
        self.chat_calls.append({"show_memory": show_memory, "copy_response": copy_response})
        return 0


class FakeOutput:
    def __init__(self) -> None:
        self.values: list[str] = []

    def emit(self, text: str) -> None:
        self.values.append(text)


class FakeRuntime:
    def __init__(self) -> None:
        self.runner = FakeRunner()
        self.output = FakeOutput()


def test_cli_parses_arguments_and_delegates_reply_to_runner():
    runtime = FakeRuntime()
    stdout = io.StringIO()
    stdin = io.StringIO("n\n")

    exit_code = main(
        ["reply", "--text", "Hello", "--copy"],
        runtime=runtime,
        stdin=stdin,
        stdout=stdout,
    )

    assert exit_code == 0
    assert len(runtime.runner.reply_calls) == 1
    request = runtime.runner.reply_calls[0]
    assert request.text == "Hello"
    assert request.copy_response is True
    assert request.show_memory is False


def test_cli_delegates_chat_mode_to_runner():
    runtime = FakeRuntime()

    exit_code = main(["chat", "--show-memory"], runtime=runtime)

    assert exit_code == 0
    assert runtime.runner.chat_calls == [{"show_memory": True, "copy_response": False}]


def test_cli_routes_interrupt_message_through_output_sink():
    runtime = FakeRuntime()

    def interrupting_run_reply(request):
        raise KeyboardInterrupt

    runtime.runner.run_reply = interrupting_run_reply

    exit_code = main(["reply", "--text", "Hello"], runtime=runtime)

    assert exit_code == 130
    assert runtime.output.values == ["Interrupted. Exiting safely."]
