use core_contracts::router::{RouteEnvelope, RouterErrorEnvelope};
use core_contracts::runtime::SessionReply;
use core_contracts::terminal::ExecJsonEnvelope;

#[test]
fn serialization_parity_route_envelope_deserializes_from_python_fixture() {
    let raw = include_str!("../../../tests/contracts/router/route_envelope.json");
    let parsed = RouteEnvelope::from_json_str(raw).unwrap();

    assert_eq!(parsed.kind, "route");
    assert_eq!(parsed.snapshot_version, "fixture-snapshot-v1");
    assert_eq!(parsed.route, "tool_execution");
    assert_eq!(parsed.payload.tool_name, "python");
    assert_eq!(parsed.payload.argv, vec!["python".to_string()]);
}

#[test]
fn serialization_parity_router_error_envelope_deserializes_from_python_fixture() {
    let raw = include_str!("../../../tests/contracts/router/router_error_envelope.json");
    let parsed = RouterErrorEnvelope::from_json_str(raw).unwrap();

    assert_eq!(parsed.kind, "router_error");
    assert_eq!(parsed.error_code, "snapshot_version_mismatch");
    assert_eq!(parsed.request_id, "router-error-fixture");
    assert_eq!(
        parsed
            .diagnostics
            .get("active_snapshot_version")
            .map(String::as_str),
        Some("fixture-snapshot-v1")
    );
}

#[test]
fn serialization_parity_exec_json_deserializes_from_python_fixture() {
    let raw = include_str!("../../../tests/contracts/terminal/exec_json.json");
    let parsed = ExecJsonEnvelope::from_json_str(raw).unwrap();

    assert_eq!(parsed.kind, "route");
    assert_eq!(parsed.intent, "tool_execution");
    assert_eq!(parsed.payload.shell, "powershell");
    assert_eq!(parsed.resolver_path.last().map(String::as_str), Some("evaluate_confidence"));
}

#[test]
fn serialization_parity_session_reply_deserializes_from_python_fixture() {
    let raw = include_str!("../../../tests/contracts/runtime/session_reply.json");
    let parsed = SessionReply::from_json_str(raw).unwrap();

    assert_eq!(parsed.event, "interaction");
    assert_eq!(parsed.provider, "stub");
    assert_eq!(parsed.timestamp, "2026-04-19T00:07:07.380448+00:00");
    assert_eq!(parsed.model, "gpt-oss-120b");
    assert_eq!(parsed.request.input, "Export the current Python runtime session reply fixture.");
    assert_eq!(parsed.request.messages.len(), 2);
    assert_eq!(parsed.request.messages[0].role, "system");
    assert_eq!(parsed.request.messages[1].role, "user");
    assert_eq!(parsed.response.content, "Stub response");
    assert_eq!(parsed.response.finish_reason, "stop");
    assert!(parsed.response.usage.is_none());
}
