from __future__ import annotations

import io
import json

from local_ai_agent.config import Settings
from local_ai_agent.modules.registry import ModuleRegistry
from local_ai_agent.modules.snapshot_builder import build_registry_snapshot
from local_ai_agent.router.events import RouterRequestReceived
from local_ai_agent.router.request import TerminalRequest
from local_ai_agent.tools.registry import ToolRegistry


def test_build_runtime_injects_router_runtime_without_breaking_contract(tmp_path, monkeypatch):
    from local_ai_agent.runtime import AppRuntime, build_runtime

    monkeypatch.setattr("local_ai_agent.runtime.build_multimodal_input_processor", lambda settings: object())

    settings = Settings(
        provider="stub",
        api_key="test-key",
        session_id="sess-1",
        logs_dir=tmp_path / "logs",
    )

    runtime = build_runtime(settings, stdin=io.StringIO(""), stdout=io.StringIO())

    assert isinstance(runtime, AppRuntime)
    assert runtime.runner is not None
    assert runtime.output is not None
    assert runtime.router_runtime is not None
    assert runtime.router_runtime.snapshot_provider is not None
    assert runtime.router_runtime.snapshot_provider.get_snapshot(session_id="sess-1") == runtime.router_runtime.snapshot
    assert runtime.router_runtime.snapshot.snapshot_version != "generated"

    request = TerminalRequest(
        request_id="req-1",
        session_id="sess-1",
        shell="powershell",
        raw_input="gh --version",
        cwd="C:\\repo",
        snapshot_version=runtime.router_runtime.snapshot.snapshot_version,
        requested_mode="json",
    )

    runtime.router_runtime.resolve(request)

    assert (settings.logs_dir / "router" / "sess-1.jsonl").exists()


def test_build_registry_snapshot_generates_stable_session_version():
    tool_registry = ToolRegistry()
    module_registry = ModuleRegistry()

    snapshot_a = build_registry_snapshot(
        session_id="sess-1",
        tool_registry=tool_registry,
        module_registry=module_registry,
    )
    snapshot_b = build_registry_snapshot(
        session_id="sess-1",
        tool_registry=tool_registry,
        module_registry=module_registry,
    )
    snapshot_other_session = build_registry_snapshot(
        session_id="sess-2",
        tool_registry=tool_registry,
        module_registry=module_registry,
    )

    assert snapshot_a.snapshot_version == snapshot_b.snapshot_version
    assert snapshot_a.snapshot_version != "generated"
    assert snapshot_a.snapshot_version != snapshot_other_session.snapshot_version


def test_jsonl_router_event_sink_persists_events_to_disk(tmp_path):
    from local_ai_agent.router.runtime_services import JsonlRouterEventSink

    sink = JsonlRouterEventSink(log_path=tmp_path / "router" / "sess-1.jsonl")

    sink.emit(
        RouterRequestReceived(
            request_id="req-1",
            session_id="sess-1",
            request_snapshot_version="snap-1",
            shell="powershell",
            raw_input="gh --version",
        )
    )

    payload = json.loads((tmp_path / "router" / "sess-1.jsonl").read_text(encoding="utf-8").splitlines()[0])

    assert payload["event_name"] == "router.request_received"
    assert payload["request_id"] == "req-1"
    assert payload["session_id"] == "sess-1"
