from dataclasses import dataclass

from local_ai_agent.models import ChatMessage


@dataclass
class FakeAgentResult:
    normalized_input: str
    response_text: str
    memory_snapshot: list[ChatMessage]
    log_path: object | None


class FakeAgent:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run_once(self, raw_text: str) -> FakeAgentResult:
        self.calls.append(raw_text)
        return FakeAgentResult(
            normalized_input=raw_text.strip(),
            response_text="Draft reply",
            memory_snapshot=[ChatMessage(role="user", content=raw_text.strip())],
            log_path=None,
        )


class FakeInputSource:
    def __init__(self, text: str) -> None:
        self.text = text

    def read(self) -> str:
        return self.text


class FakeOutputSink:
    def __init__(self) -> None:
        self.values: list[str] = []

    def emit(self, text: str) -> None:
        self.values.append(text)


class FakeClipboard:
    def __init__(self) -> None:
        self.values: list[str] = []

    def copy(self, text: str) -> None:
        self.values.append(text)


class FakeConfirmationPolicy:
    def __init__(self, answers: list[bool]) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []

    def confirm(self, prompt: str) -> bool:
        self.prompts.append(prompt)
        return self.answers.pop(0)


def test_session_runner_resolves_text_runs_agent_and_routes_outputs():
    from local_ai_agent.session_runner import AgentSessionRunner, ReplyRequest

    agent = FakeAgent()
    output = FakeOutputSink()
    clipboard = FakeClipboard()
    confirm = FakeConfirmationPolicy([False])
    runner = AgentSessionRunner(agent=agent, output=output, clipboard=clipboard, confirmer=confirm)

    result = runner.run_reply(
        ReplyRequest(
            text=None,
            input_source=FakeInputSource("Hello from source"),
            copy_response=True,
            show_memory=True,
        )
    )

    assert agent.calls == ["Hello from source"]
    assert output.values == [
        "Draft reply",
        "Clipboard copy skipped.",
        "Memory:",
        "- user: Hello from source",
    ]
    assert clipboard.values == []
    assert confirm.prompts == ["Copy response to clipboard?"]
    assert result.exit_code == 0


class FakeStreamingInputSource:
    def __init__(self, values: list[str]) -> None:
        self.values = list(values)

    def read(self) -> str:
        if not self.values:
            return ""
        return self.values.pop(0)


def test_session_runner_owns_chat_loop_and_exit_behavior():
    from local_ai_agent.session_runner import AgentSessionRunner

    agent = FakeAgent()
    output = FakeOutputSink()
    runner = AgentSessionRunner(
        agent=agent,
        output=output,
        input_source=FakeStreamingInputSource(["First turn", "/exit"]),
    )

    exit_code = runner.run_chat(show_memory=True)

    assert exit_code == 0
    assert agent.calls == ["First turn"]
    assert output.values == [
        "Interactive session started. Type /exit to quit.",
        "Agent> Draft reply",
        "Memory:",
        "- user: First turn",
        "Session closed.",
    ]
