use std::fs;
use std::fs::File;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

use core_contracts::router::RouteEnvelope;

#[test]
fn route_command_parity_defaults_to_python_backend_without_flag() {
    let stdout = run_route_command("command_fix", None);
    let parsed = RouteEnvelope::from_json_str(&stdout).unwrap();

    assert_eq!(parsed.route, "command_fix");
    assert_eq!(parsed.resolver_path, vec!["fixture_stub".to_string()]);
    assert_eq!(parsed.evidence, vec!["fixture:command_fix".to_string()]);
}

#[test]
fn route_command_parity_uses_rust_backend_when_flag_enabled() {
    let stdout = run_route_command("command_fix", Some(("COPILOTTRAE_ROUTE_BACKEND", "rust")));
    let parsed = RouteEnvelope::from_json_str(&stdout).unwrap();

    assert_eq!(parsed.route, "command_fix");
    assert_eq!(
        parsed.resolver_path,
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
    assert_eq!(parsed.evidence, vec!["alias_match:github-cli".to_string()]);
}

fn run_route_command(fixture: &str, env: Option<(&str, &str)>) -> String {
    let stdout_path = temp_stdout_path();
    let stdout_file = File::create(&stdout_path).unwrap();
    let mut command = Command::new(compiled_cli_binary());

    command.args(["route", "--fixture", fixture]).stdout(stdout_file);
    if let Some((key, value)) = env {
        command.env(key, value);
    } else {
        command.env_remove("COPILOTTRAE_ROUTE_BACKEND");
    }

    let status = command.status().unwrap();
    assert!(status.success());

    fs::read_to_string(&stdout_path).unwrap()
}

fn compiled_cli_binary() -> std::path::PathBuf {
    let deps_dir = std::env::current_exe().unwrap();
    let debug_dir = deps_dir.parent().unwrap().parent().unwrap();
    debug_dir.join(if cfg!(windows) { "cli-app.exe" } else { "cli-app" })
}

fn temp_stdout_path() -> std::path::PathBuf {
    let unique = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();

    std::env::temp_dir().join(format!("cli-app-route-parity-{unique}.json"))
}
