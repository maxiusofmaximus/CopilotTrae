from local_ai_agent.router.errors import RouterErrorEnvelope
from local_ai_agent.router.request import TerminalRequest
from local_ai_agent.router.snapshot import RegistrySnapshot
from local_ai_agent.runtime import RouterRuntime


class RecordingEventSink:
    def __init__(self) -> None:
        self.events: list[object] = []

    def emit(self, event: object) -> None:
        self.events.append(event)


class SpyRouter:
    def __init__(self, result: object) -> None:
        self.result = result

    def resolve(self, request: TerminalRequest, snapshot: RegistrySnapshot) -> object:
        return self.result


class StaticSnapshotProvider:
    def __init__(self, snapshot: RegistrySnapshot) -> None:
        self.snapshot = snapshot

    def get_snapshot(self, session_id: str) -> RegistrySnapshot:
        assert session_id == self.snapshot.built_for_session
        return self.snapshot


def test_runtime_emits_typed_error_event_for_router_errors():
    from local_ai_agent.router.events import RouterErrorEmitted, RouterRequestReceived, RouterSnapshotBound

    snapshot = RegistrySnapshot.minimal(snapshot_version="snap-1", built_for_session="sess-1")
    request = TerminalRequest(
        request_id="req-3",
        session_id="sess-1",
        shell="powershell",
        raw_input="gh --version",
        cwd="C:\\repo",
        snapshot_version="snap-stale",
    )
    error = RouterErrorEnvelope(
        error_code="snapshot_version_mismatch",
        request_id="req-3",
        session_id="sess-1",
        snapshot_version="snap-1",
        diagnostics={"request_snapshot_version": "snap-stale"},
    )
    sink = RecordingEventSink()
    runtime = RouterRuntime(
        router=SpyRouter(error),
        snapshot_provider=StaticSnapshotProvider(snapshot),
        event_sink=sink,
        default_session_id="sess-1",
    )

    result = runtime.resolve(request)

    assert result is error
    assert [type(event) for event in sink.events] == [
        RouterRequestReceived,
        RouterSnapshotBound,
        RouterErrorEmitted,
    ]
    assert sink.events[2].event_name == "router.error_emitted"
    assert sink.events[2].error_code == "snapshot_version_mismatch"
