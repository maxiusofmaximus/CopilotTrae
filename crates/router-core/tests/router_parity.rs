use core_contracts::router::{
    RouteEnvelope as FixtureRouteEnvelope, RouterErrorEnvelope as FixtureRouterErrorEnvelope,
};
use router_core::{
    DeterministicRouter, JsonObject, JsonValue, RegistrySnapshot, RouteResolution, TerminalRequest,
};

#[test]
fn router_parity_tool_execution_matches_real_task2_fixture() {
    let fixture = FixtureRouteEnvelope::from_json_str(include_str!(
        "../../../tests/contracts/router/route_envelope.json"
    ))
    .unwrap();
    let router = DeterministicRouter::default();
    let snapshot = RegistrySnapshot {
        snapshot_version: fixture.snapshot_version.clone(),
        built_for_session: "fixture-export".to_string(),
        built_at: String::new(),
        tools: vec![],
        modules: vec![],
        policies: JsonObject::new(),
        source_versions: JsonObject::new(),
        execution_surface: JsonObject::from([(
            "tools".to_string(),
            JsonValue::Array(vec![JsonValue::Object(JsonObject::from([
                (
                    "tool_name".to_string(),
                    JsonValue::String(fixture.payload.tool_name.clone()),
                ),
                (
                    "shell".to_string(),
                    JsonValue::String(fixture.payload.shell.clone()),
                ),
                ("available".to_string(), JsonValue::Bool(true)),
            ]))]),
        )]),
        capability_surface: JsonObject::new(),
        extensions: JsonObject::new(),
    };
    let request = TerminalRequest {
        request_id: "router-fixture".to_string(),
        session_id: "fixture-export".to_string(),
        shell: fixture.payload.shell.clone(),
        raw_input: fixture.payload.argv.join(" "),
        cwd: "C:\\repo".to_string(),
        snapshot_version: fixture.snapshot_version.clone(),
    };

    let result = router.resolve(&request, &snapshot);

    match result {
        RouteResolution::Route(route) => {
            assert_eq!(route.kind, fixture.kind);
            assert_eq!(route.snapshot_version, fixture.snapshot_version);
            assert_eq!(route.route, fixture.route);
            assert_eq!(route.intent, fixture.intent);
            assert_eq!(route.payload.tool_name(), Some(fixture.payload.tool_name.as_str()));
            assert_eq!(route.payload.shell(), Some(fixture.payload.shell.as_str()));
            assert_eq!(route.payload.argv(), Some(fixture.payload.argv.as_slice()));
            assert_eq!(route.evidence, fixture.evidence);
            assert_eq!(route.confidence, fixture.confidence);
            assert_eq!(route.threshold_applied, fixture.threshold_applied);
            assert_eq!(route.threshold_source, fixture.threshold_source);
            assert_eq!(route.resolver_path, fixture.resolver_path);
        }
        RouteResolution::Error(error) => panic!("expected route fixture parity, got error {}", error.error_code),
    }
}

#[test]
fn router_parity_snapshot_mismatch_matches_real_task2_fixture() {
    let fixture = FixtureRouterErrorEnvelope::from_json_str(include_str!(
        "../../../tests/contracts/router/router_error_envelope.json"
    ))
    .unwrap();
    let router = DeterministicRouter::default();
    let snapshot = RegistrySnapshot::minimal(
        fixture.snapshot_version.clone(),
        fixture.session_id.clone(),
    );
    let request = TerminalRequest {
        request_id: fixture.request_id.clone(),
        session_id: fixture.session_id.clone(),
        shell: "powershell".to_string(),
        raw_input: "python".to_string(),
        cwd: "C:\\repo".to_string(),
        snapshot_version: fixture
            .diagnostics
            .get("request_snapshot_version")
            .cloned()
            .unwrap(),
    };

    let result = router.resolve(&request, &snapshot);

    match result {
        RouteResolution::Error(error) => {
            assert_eq!(error.kind, fixture.kind);
            assert_eq!(error.snapshot_version, fixture.snapshot_version);
            assert_eq!(error.error_code, fixture.error_code);
            assert_eq!(error.request_id, fixture.request_id);
            assert_eq!(error.session_id, fixture.session_id);
            assert_eq!(error.diagnostics, fixture.diagnostics);
        }
        RouteResolution::Route(route) => panic!("expected router error fixture parity, got route {}", route.route),
    }
}

#[test]
fn router_parity_command_fix_tracks_only_executed_steps() {
    let router = DeterministicRouter::default();
    let snapshot = RegistrySnapshot {
        snapshot_version: "snap-1".to_string(),
        built_for_session: "sess-1".to_string(),
        built_at: String::new(),
        tools: vec![],
        modules: vec![],
        policies: JsonObject::new(),
        source_versions: JsonObject::new(),
        execution_surface: JsonObject::from([(
            "tools".to_string(),
            JsonValue::Array(vec![JsonValue::Object(JsonObject::from([
                ("tool_name".to_string(), JsonValue::String("gh".to_string())),
                ("shell".to_string(), JsonValue::String("powershell".to_string())),
                ("available".to_string(), JsonValue::Bool(true)),
                (
                    "aliases".to_string(),
                    JsonValue::Array(vec![JsonValue::String("github-cli".to_string())]),
                ),
            ]))]),
        )]),
        capability_surface: JsonObject::new(),
        extensions: JsonObject::new(),
    };
    let request = TerminalRequest {
        request_id: "req-fix".to_string(),
        session_id: "sess-1".to_string(),
        shell: "powershell".to_string(),
        raw_input: "github.cli --version".to_string(),
        cwd: "C:\\repo".to_string(),
        snapshot_version: "snap-1".to_string(),
    };

    let result = router.resolve(&request, &snapshot);

    match result {
        RouteResolution::Route(route) => {
            assert_eq!(route.route, "command_fix");
            assert_eq!(route.intent, "correction");
            assert_eq!(route.payload.suggested_command(), Some("gh --version"));
            assert_eq!(route.evidence, vec!["alias_match:github-cli".to_string()]);
            assert_eq!(route.threshold_applied, 0.90);
            assert_eq!(route.threshold_source, "intent:command_fix");
            assert_eq!(
                route.resolver_path,
                vec![
                    "normalize_input".to_string(),
                    "parse_command_shape".to_string(),
                    "classify_intent".to_string(),
                    "resolve_local_candidates".to_string(),
                    "apply_deterministic_rules".to_string(),
                    "fixes.collect_alias_matches".to_string(),
                    "fixes.collect_suffix_matches".to_string(),
                    "fixes.rank_candidates".to_string(),
                    "evaluate_confidence".to_string(),
                ]
            );
        }
        RouteResolution::Error(error) => panic!("expected command_fix route, got error {}", error.error_code),
    }
}
