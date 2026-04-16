from local_ai_agent.router.output import EnvelopeMetadata, RouteEnvelope
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
        self.calls: list[tuple[TerminalRequest, RegistrySnapshot]] = []

    def resolve(self, request: TerminalRequest, snapshot: RegistrySnapshot) -> object:
        self.calls.append((request, snapshot))
        return self.result


def test_runtime_binds_request_to_single_snapshot_and_emits_events():
    from local_ai_agent.router.events import (
        RouterIntentClassified,
        RouterRequestReceived,
        RouterRouteEmitted,
        RouterSnapshotBound,
    )

    snapshot = RegistrySnapshot.minimal(snapshot_version="snap-1", built_for_session="sess-1")
    request = TerminalRequest(
        request_id="req-1",
        session_id="sess-1",
        shell="powershell",
        raw_input="gh --version",
        cwd="C:\\repo",
        snapshot_version="snap-1",
    )
    route = RouteEnvelope.tool_execution(
        intent="tool_execution",
        snapshot_version="snap-1",
        tool_name="gh",
        shell="powershell",
        argv=["gh", "--version"],
        confidence=1.0,
        threshold_applied=0.93,
        threshold_source="intent:execution",
        resolver_path=["normalize_input", "evaluate_confidence"],
        evidence=["tool_name_match:gh"],
    )
    sink = RecordingEventSink()
    router = SpyRouter(route)
    runtime = RouterRuntime(router=router, snapshot=snapshot, event_sink=sink)

    result = runtime.resolve(request)

    assert result is route
    assert router.calls == [(request, snapshot)]
    assert set(RouterRuntime.__dataclass_fields__) == {"router", "snapshot", "event_sink"}
    assert [type(event) for event in sink.events] == [
        RouterRequestReceived,
        RouterSnapshotBound,
        RouterIntentClassified,
        RouterRouteEmitted,
    ]
    assert sink.events[0].event_name == "router.request_received"
    assert sink.events[1].event_name == "router.snapshot_bound"
    assert sink.events[2].intent == "tool_execution"
    assert sink.events[3].route == "tool_execution"


def test_runtime_serializes_hub_proposals_without_executing_actions():
    snapshot = RegistrySnapshot.minimal(snapshot_version="snap-1", built_for_session="sess-1")
    request = TerminalRequest(
        request_id="req-2",
        session_id="sess-1",
        shell="powershell",
        raw_input="need ripgrep",
        cwd="C:\\repo",
        snapshot_version="snap-1",
    )
    hub_install = RouteEnvelope(
        envelope=EnvelopeMetadata(kind="route", snapshot_version="snap-1"),
        route="hub_install",
        intent="installation",
        payload={"proposal": {"package": "ripgrep", "source": "hub"}},
        evidence=["missing_capability:search"],
        confidence=0.85,
        threshold_applied=0.85,
        threshold_source="intent:installation",
        resolver_path=["normalize_input", "evaluate_capability_gap"],
    )
    hub_action = RouteEnvelope(
        envelope=EnvelopeMetadata(kind="route", snapshot_version="snap-1"),
        route="hub_action_proposal",
        intent="installation",
        payload={"proposal": {"action": "open_hub", "target": "ripgrep"}},
        evidence=["operator_confirmation_required"],
        confidence=0.80,
        threshold_applied=0.85,
        threshold_source="intent:installation",
        resolver_path=["normalize_input", "evaluate_capability_gap"],
    )

    install_runtime = RouterRuntime(router=SpyRouter(hub_install), snapshot=snapshot, event_sink=RecordingEventSink())
    action_runtime = RouterRuntime(router=SpyRouter(hub_action), snapshot=snapshot, event_sink=RecordingEventSink())

    install_payload = install_runtime.resolve_serialized(request)
    action_payload = action_runtime.resolve_serialized(request)

    assert install_payload["route"] == "hub_install"
    assert install_payload["payload"]["proposal"]["package"] == "ripgrep"
    assert action_payload["route"] == "hub_action_proposal"
    assert action_payload["payload"]["proposal"]["action"] == "open_hub"
