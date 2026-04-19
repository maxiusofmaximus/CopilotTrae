pub fn run(args: &[String]) -> Result<String, String> {
    match args {
        [command, option, fixture] if command == "route" && option == "--fixture" => {
            Ok(route_fixture(fixture))
        }
        _ => Err("usage: cli-app route --fixture <name>".to_string()),
    }
}

fn route_fixture(name: &str) -> String {
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
