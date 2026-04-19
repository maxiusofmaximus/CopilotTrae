from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from local_ai_agent.agent import AgentController
from local_ai_agent.cli import main
from local_ai_agent.config import Settings
from local_ai_agent.logging_utils import InteractionLogger
from local_ai_agent.memory import ConversationMemory
from local_ai_agent.output_adapters import ConsoleOutputSink
from local_ai_agent.providers import build_provider
from local_ai_agent.router.pipeline import DeterministicRouter
from local_ai_agent.router.request import TerminalRequest
from local_ai_agent.router.runtime_services import CachedSnapshotProvider, JsonlRouterEventSink
from local_ai_agent.router.snapshot import RegistrySnapshot
from local_ai_agent.runtime import RouterRuntime
from local_ai_agent.session_runner import AgentSessionRunner, ReplyRequest, serialize_router_envelope

FIXTURE_ROOT = Path("tests/contracts")


def ensure_fixture_layout() -> None:
    for relative_path in ("router", "terminal", "runtime"):
        (FIXTURE_ROOT / relative_path).mkdir(parents=True, exist_ok=True)


def write_fixture(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def export_fixtures() -> None:
    ensure_fixture_layout()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        settings = Settings(
            provider="stub",
            session_id="fixture-export",
            logs_dir=temp_root / "logs",
            confirm_before_copy=False,
        )

        route_runtime = build_fixture_router_runtime(settings)
        tool_name = "python"
        cwd = str(Path.cwd())

        route_request = TerminalRequest(
            request_id="route-envelope-fixture",
            session_id=settings.session_id,
            shell="powershell",
            raw_input=tool_name,
            cwd=cwd,
            snapshot_version=route_runtime.snapshot.snapshot_version,
        )
        write_fixture(
            FIXTURE_ROOT / "router" / "route_envelope.json",
            route_runtime.resolve_serialized(route_request),
        )

        router_error_request = TerminalRequest(
            request_id="router-error-fixture",
            session_id=settings.session_id,
            shell="powershell",
            raw_input=tool_name,
            cwd=cwd,
            snapshot_version="stale-snapshot-version",
        )
        router_error_payload = serialize_router_envelope(route_runtime.resolve(router_error_request))
        write_fixture(FIXTURE_ROOT / "router" / "router_error_envelope.json", router_error_payload)

        exec_stdout = io.StringIO()
        exit_code = main(
            [
                "exec",
                "--json",
                "--shell",
                "powershell",
                "--cwd",
                cwd,
                tool_name,
            ],
            runtime=SimpleNamespace(router_runtime=route_runtime),
            stdout=exec_stdout,
            stderr=io.StringIO(),
        )
        if exit_code != 0:
            raise RuntimeError(f"exec --json export failed with exit code {exit_code}")
        write_fixture(
            FIXTURE_ROOT / "terminal" / "exec_json.json",
            json.loads(exec_stdout.getvalue()),
        )

        reply_log_entry = capture_session_reply_log_entry(settings)
        write_fixture(FIXTURE_ROOT / "runtime" / "session_reply.json", reply_log_entry)


def build_fixture_router_runtime(settings: Settings) -> RouterRuntime:
    snapshot = RegistrySnapshot(
        snapshot_version="fixture-snapshot-v1",
        built_for_session=settings.session_id,
        execution_surface={
            "tools": [
                {
                    "tool_name": "python",
                    "adapter_name": "generic_cli",
                    "shell": "powershell",
                    "available": True,
                    "aliases": ["python3"],
                    "capabilities": ["version"],
                }
            ]
        },
        capability_surface={"capabilities": ("tool_execution", "command_fix")},
    )
    return RouterRuntime(
        router=DeterministicRouter(),
        snapshot_provider=CachedSnapshotProvider(snapshot_factory=lambda session_id: snapshot),
        event_sink=JsonlRouterEventSink(settings.logs_dir / "router" / f"{settings.session_id}.jsonl"),
        default_session_id=settings.session_id,
    )


def capture_session_reply_log_entry(settings: Settings) -> dict[str, object]:
    output_stream = io.StringIO()
    output = ConsoleOutputSink(output_stream)
    agent = AgentController(
        settings=settings,
        llm_client=build_provider(settings),
        memory=ConversationMemory(
            max_messages=settings.max_memory_messages,
            system_prompt=settings.system_prompt,
        ),
        logger=InteractionLogger(logs_dir=settings.logs_dir, session_id=settings.session_id),
    )
    runner = AgentSessionRunner(agent=agent, output=output)
    result = runner.run_reply(ReplyRequest(text="Export the current Python runtime session reply fixture."))
    if result.log_path is None:
        raise RuntimeError("Session reply fixture export did not produce a log entry.")

    entries = result.log_path.read_text(encoding="utf-8").splitlines()
    if not entries:
        raise RuntimeError("Session reply fixture export produced an empty log file.")
    return json.loads(entries[-1])


if __name__ == "__main__":
    export_fixtures()
