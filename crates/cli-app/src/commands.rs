use router_core::{
    DeterministicRouter, JsonObject, JsonValue, RegistrySnapshot, RouteEnvelope, RoutePayload,
    RouteResolution, TerminalRequest,
};

const ROUTE_BACKEND_ENV: &str = "COPILOTTRAE_ROUTE_BACKEND";

pub fn run(args: &[String]) -> Result<String, String> {
    match args {
        [command, option, fixture] if command == "route" && option == "--fixture" => {
            route_fixture(fixture)
        }
        _ => Err("usage: cli-app route --fixture <name>".to_string()),
    }
}

fn route_fixture(name: &str) -> Result<String, String> {
    if use_rust_route_backend() {
        return route_fixture_rust(name);
    }

    Ok(route_fixture_python(name))
}

fn use_rust_route_backend() -> bool {
    std::env::var(ROUTE_BACKEND_ENV)
        .map(|value| value.eq_ignore_ascii_case("rust"))
        .unwrap_or(false)
}

fn route_fixture_rust(name: &str) -> Result<String, String> {
    match name {
        "command_fix" => serialize_route_resolution(resolve_rust_command_fix_fixture()),
        _ => Ok(route_fixture_python(name)),
    }
}

fn route_fixture_python(name: &str) -> String {
    format!(
        concat!(
            "{{",
            "\"kind\":\"route\",",
            "\"snapshot_version\":\"fixture-snapshot-v1\",",
            "\"route\":\"{name}\",",
            "\"intent\":\"tool_execution\",",
            "\"payload\":{{",
            "\"tool_name\":\"python\",",
            "\"shell\":\"powershell\",",
            "\"argv\":[\"python\"]",
            "}},",
            "\"evidence\":[\"fixture:{name}\"],",
            "\"confidence\":1.0,",
            "\"threshold_applied\":0.93,",
            "\"threshold_source\":\"intent:execution\",",
            "\"resolver_path\":[\"fixture_stub\"]",
            "}}"
        ),
        name = escape_json_string(name)
    )
}

fn resolve_rust_command_fix_fixture() -> RouteResolution {
    let router = DeterministicRouter::default();
    let snapshot_version = "fixture-snapshot-v1".to_string();
    let session_id = "fixture-export".to_string();
    let snapshot = RegistrySnapshot {
        snapshot_version: snapshot_version.clone(),
        built_for_session: session_id.clone(),
        built_at: String::new(),
        tools: vec![],
        modules: vec![],
        policies: JsonObject::new(),
        source_versions: JsonObject::new(),
        execution_surface: JsonObject::from([(
            "tools".to_string(),
            JsonValue::Array(vec![JsonValue::Object(JsonObject::from([
                ("tool_name".to_string(), JsonValue::String("gh".to_string())),
                (
                    "shell".to_string(),
                    JsonValue::String("powershell".to_string()),
                ),
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
        request_id: "route-fixture".to_string(),
        session_id,
        shell: "powershell".to_string(),
        raw_input: "github.cli --version".to_string(),
        cwd: "C:\\repo".to_string(),
        snapshot_version,
    };

    router.resolve(&request, &snapshot)
}

fn serialize_route_resolution(resolution: RouteResolution) -> Result<String, String> {
    match resolution {
        RouteResolution::Route(route) => Ok(serialize_route_envelope(&route)),
        RouteResolution::Error(error) => Err(format!(
            "failed to resolve rust route fixture: {}",
            error.error_code
        )),
    }
}

fn serialize_route_envelope(route: &RouteEnvelope) -> String {
    let (tool_name, shell, argv) = legacy_payload(route);

    format!(
        concat!(
            "{{",
            "\"kind\":\"{kind}\",",
            "\"snapshot_version\":\"{snapshot_version}\",",
            "\"route\":\"{route_name}\",",
            "\"intent\":\"{intent}\",",
            "\"payload\":{{",
            "\"tool_name\":\"{tool_name}\",",
            "\"shell\":\"{shell}\",",
            "\"argv\":[{argv}]",
            "}},",
            "\"evidence\":[{evidence}],",
            "\"confidence\":{confidence},",
            "\"threshold_applied\":{threshold_applied},",
            "\"threshold_source\":\"{threshold_source}\",",
            "\"resolver_path\":[{resolver_path}]",
            "}}"
        ),
        kind = escape_json_string(&route.kind),
        snapshot_version = escape_json_string(&route.snapshot_version),
        route_name = escape_json_string(&route.route),
        intent = escape_json_string(&route.intent),
        tool_name = escape_json_string(&tool_name),
        shell = escape_json_string(&shell),
        argv = json_string_array(&argv),
        evidence = json_string_array(&route.evidence),
        confidence = route.confidence,
        threshold_applied = route.threshold_applied,
        threshold_source = escape_json_string(&route.threshold_source),
        resolver_path = json_string_array(&route.resolver_path),
    )
}

fn legacy_payload(route: &RouteEnvelope) -> (String, String, Vec<String>) {
    match &route.payload {
        RoutePayload::ToolExecution {
            tool_name,
            shell,
            argv,
        } => (tool_name.clone(), shell.clone(), argv.clone()),
        RoutePayload::CommandFix {
            suggested_command, ..
        } => {
            let argv = split_command(suggested_command);
            let tool_name = argv.first().cloned().unwrap_or_default();
            (tool_name, "powershell".to_string(), argv)
        }
        RoutePayload::Clarification { original, .. } => {
            let argv = split_command(original);
            let tool_name = argv.first().cloned().unwrap_or_default();
            (tool_name, "powershell".to_string(), argv)
        }
    }
}

fn split_command(command: &str) -> Vec<String> {
    command
        .split_whitespace()
        .map(ToOwned::to_owned)
        .collect::<Vec<_>>()
}

fn json_string_array(values: &[String]) -> String {
    values
        .iter()
        .map(|value| format!("\"{}\"", escape_json_string(value)))
        .collect::<Vec<_>>()
        .join(",")
}

fn escape_json_string(value: &str) -> String {
    let mut escaped = String::new();

    for character in value.chars() {
        match character {
            '"' => escaped.push_str("\\\""),
            '\\' => escaped.push_str("\\\\"),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            '\t' => escaped.push_str("\\t"),
            _ => escaped.push(character),
        }
    }

    escaped
}
