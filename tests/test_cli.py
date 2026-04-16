import io
import json

from local_ai_agent.cli import main
from local_ai_agent.router.errors import RouterErrorEnvelope
from local_ai_agent.router.output import EnvelopeMetadata, RouteEnvelope


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


class FakeRouterRuntime:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[object] = []

    def resolve_serialized(self, request):
        self.calls.append(request)
        return self.payload


class FakeRuntimeWithRoute(FakeRuntime):
    def __init__(self, payload: dict[str, object]) -> None:
        super().__init__()
        self.router_runtime = FakeRouterRuntime(payload)


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


def test_cli_route_command_prints_machine_readable_router_json():
    payload = {
        "kind": "route",
        "snapshot_version": "snap-1",
        "route": "tool_execution",
        "intent": "tool_execution",
        "payload": {
            "tool_name": "gh",
            "shell": "powershell",
            "argv": ["gh", "--version"],
        },
        "evidence": ["tool_name_match:gh"],
        "confidence": 1.0,
        "threshold_applied": 0.93,
        "threshold_source": "intent:execution",
        "resolver_path": ["normalize_input", "evaluate_confidence"],
    }
    runtime = FakeRuntimeWithRoute(payload)
    stdout = io.StringIO()

    exit_code = main(
        [
            "route",
            "--text",
            "gh --version",
            "--shell",
            "powershell",
            "--cwd",
            "C:\\repo",
            "--snapshot-version",
            "snap-1",
        ],
        runtime=runtime,
        stdout=stdout,
    )

    assert exit_code == 0
    assert json.loads(stdout.getvalue()) == payload
    assert stdout.getvalue().strip() == json.dumps(payload, ensure_ascii=True)
    request = runtime.router_runtime.calls[0]
    assert request.raw_input == "gh --version"
    assert request.shell == "powershell"
    assert request.cwd == "C:\\repo"
    assert request.snapshot_version == "snap-1"
    assert runtime.runner.reply_calls == []
    assert runtime.runner.chat_calls == []
    assert runtime.output.values == []
