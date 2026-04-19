import json
import subprocess
import sys
from pathlib import Path


def test_exported_contract_fixtures_are_present_and_parseable():
    fixture_paths = {
        "route_envelope": Path("tests/contracts/router/route_envelope.json"),
        "router_error_envelope": Path("tests/contracts/router/router_error_envelope.json"),
        "exec_json": Path("tests/contracts/terminal/exec_json.json"),
        "session_reply": Path("tests/contracts/runtime/session_reply.json"),
    }

    for path in fixture_paths.values():
        if path.exists():
            path.unlink()

    result = subprocess.run(
        [sys.executable, "scripts/export_contract_fixtures.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    payloads = {}
    for name, path in fixture_paths.items():
        assert path.exists(), f"missing fixture: {name}"
        payloads[name] = json.loads(path.read_text(encoding="utf-8"))

    assert payloads["route_envelope"]["kind"] == "route"
    assert payloads["router_error_envelope"]["kind"] == "router_error"
    assert payloads["router_error_envelope"]["error_code"] == "snapshot_version_mismatch"
    assert payloads["exec_json"]["kind"] == "route"
    assert payloads["session_reply"]["event"] == "interaction"
    assert payloads["session_reply"]["response"]["content"] == "Stub response"
