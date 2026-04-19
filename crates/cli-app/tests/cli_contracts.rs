use std::fs;
use std::fs::File;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

use core_contracts::router::RouteEnvelope;

#[test]
fn cli_contracts_route_command_returns_contract_json() {
    let stdout_path = temp_stdout_path();
    let stdout_file = File::create(&stdout_path).unwrap();

    let status = Command::new(compiled_cli_binary())
        .args(["route", "--fixture", "command_fix"])
        .stdout(stdout_file)
        .status()
        .unwrap();

    assert!(status.success());

    let stdout = fs::read_to_string(&stdout_path).unwrap();
    let parsed = RouteEnvelope::from_json_str(&stdout).unwrap();

    assert_eq!(parsed.kind, "route");
    assert_eq!(parsed.route, "command_fix");
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

    std::env::temp_dir().join(format!("cli-app-route-{unique}.json"))
}
