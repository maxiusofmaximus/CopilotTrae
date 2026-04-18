from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MIDDLEWARE_PATH = REPO_ROOT / "scripts" / "powershell" / "middleware.ps1"


def _write_cmd(path: Path, body: str) -> None:
    path.write_text("@echo off\r\n" + body.strip() + "\r\n", encoding="utf-8")


def _write_router_stub(path: Path, log_path: Path, routes: dict[str, dict[str, object]]) -> None:
    payload = json.dumps(routes)
    script = "\n".join(
        [
            "from __future__ import annotations",
            "import json",
            "import os",
            "import sys",
            f"routes = json.loads({payload!r})",
            "log_path = os.environ['MIDDLEWARE_LOG']",
            "argv = sys.argv[1:]",
            "with open(log_path, 'a', encoding='utf-8') as handle:",
            "    handle.write(' '.join(argv) + '\\n')",
            "if len(argv) >= 2 and argv[0] == 'exec' and argv[1] == '--json':",
            "    command_text = ' '.join(argv[6:])",
            "    route = routes.get(command_text)",
            "    if route is None:",
            "        print(json.dumps({",
            "            'kind': 'route',",
            "            'snapshot_version': 'snap-test',",
            "            'route': 'reject',",
            "            'intent': 'unknown',",
            "            'payload': {'reason': 'no deterministic fix available'},",
            "            'evidence': ['test:no_match'],",
            "            'confidence': 1.0,",
            "            'threshold_applied': 1.0,",
            "            'threshold_source': 'test',",
            "            'resolver_path': ['test']",
            "        }))",
            "        raise SystemExit(0)",
            "    print(json.dumps(route))",
            "    raise SystemExit(0)",
            "if argv[:4] == ['exec', '--shell', 'powershell', '--cwd']:",
            "    command_text = ' '.join(argv[5:])",
            "    route = routes.get(command_text)",
            "    if route and route.get('route') == 'command_fix':",
            "        suggestion = route['payload']['suggested_command']",
            "        print('Command not found.')",
            "        print()",
            "        print('Suggested command:')",
            "        print(suggestion)",
            "        print()",
            "        print(f'Executed suggested command: {suggestion}')",
            "        raise SystemExit(0)",
            "    print('Execution blocked: no deterministic fix available')",
            "    raise SystemExit(1)",
            "print('unexpected invocation: ' + ' '.join(argv), file=sys.stderr)",
            "raise SystemExit(90)",
        ]
    )
    path.write_text(script, encoding="utf-8")
    _write_cmd(path.with_suffix(".cmd"), f'"{sys.executable}" "{path}" %*' + "\r\nexit /b %ERRORLEVEL%")


def _run_middleware(
    command: list[str],
    *,
    bin_dir: Path,
    log_path: Path,
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["MIDDLEWARE_LOG"] = str(log_path)
    return subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(MIDDLEWARE_PATH), *command],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        input=stdin_text,
        env=env,
        check=False,
    )


def _read_log_lines(log_path: Path) -> list[str]:
    if not log_path.exists():
        return []
    return log_path.read_text(encoding="utf-8").splitlines()


def test_real_usage_typo_commands_route_to_deterministic_corrections(tmp_path: Path) -> None:
    """Daily shell typos should be routed only after the original command fails."""

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "usage.log"
    routes = {
        "github.cli --version": {
            "kind": "route",
            "snapshot_version": "snap-test",
            "route": "command_fix",
            "intent": "correction",
            "payload": {"original": "github.cli --version", "suggested_command": "gh --version"},
            "evidence": ["alias_match:github-cli"],
            "confidence": 1.0,
            "threshold_applied": 0.9,
            "threshold_source": "intent:command_fix",
            "resolver_path": ["test"],
        },
        "gti status": {
            "kind": "route",
            "snapshot_version": "snap-test",
            "route": "command_fix",
            "intent": "correction",
            "payload": {"original": "gti status", "suggested_command": "git status"},
            "evidence": ["transpose_match:gti"],
            "confidence": 1.0,
            "threshold_applied": 0.9,
            "threshold_source": "intent:command_fix",
            "resolver_path": ["test"],
        },
        "npx.cli create-next-app demo": {
            "kind": "route",
            "snapshot_version": "snap-test",
            "route": "command_fix",
            "intent": "correction",
            "payload": {"original": "npx.cli create-next-app demo", "suggested_command": "npx create-next-app demo"},
            "evidence": ["alias_match:npx-cli"],
            "confidence": 1.0,
            "threshold_applied": 0.9,
            "threshold_source": "intent:command_fix",
            "resolver_path": ["test"],
        },
    }
    _write_router_stub(bin_dir / "local-ai-agent.py", log_path, routes)

    for typo in routes:
        result = _run_middleware(typo.split(" "), bin_dir=bin_dir, log_path=log_path)
        assert result.returncode == 0
        assert "Router route: command_fix" in result.stdout
        assert "Suggested command:" in result.stdout


def test_real_usage_valid_commands_never_touch_the_router(tmp_path: Path) -> None:
    """Commands a developer runs every day should stay transparent when they already exist."""

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "usage.log"
    _write_router_stub(bin_dir / "local-ai-agent.py", log_path, {})
    _write_cmd(bin_dir / "git.cmd", "echo git-ok\r\nexit /b 0")
    _write_cmd(bin_dir / "python.cmd", "echo python-ok\r\nexit /b 0")
    _write_cmd(bin_dir / "gh.cmd", "echo gh-ok\r\nexit /b 0")

    for command in (["git", "status"], ["python", "--version"], ["gh", "repo", "list"]):
        result = _run_middleware(command, bin_dir=bin_dir, log_path=log_path)
        assert result.returncode == 0
        assert "Router route:" not in result.stdout

    assert _read_log_lines(log_path) == []


def test_real_usage_correct_flags_stay_on_the_happy_path(tmp_path: Path) -> None:
    """Known binaries with already-correct flags should not be second-guessed by routing."""

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "usage.log"
    _write_router_stub(bin_dir / "local-ai-agent.py", log_path, {})
    _write_cmd(bin_dir / "gh.cmd", "echo gh version 9.9.9\r\nexit /b 0")

    result = _run_middleware(["gh", "--version"], bin_dir=bin_dir, log_path=log_path)

    assert result.returncode == 0
    assert "gh version 9.9.9" in result.stdout
    assert "Router route:" not in result.stdout
    assert _read_log_lines(log_path) == []


def test_real_usage_unknown_command_surfaces_no_fix_when_router_cannot_help(tmp_path: Path) -> None:
    """Totally unknown commands should fail clearly instead of pretending a fix exists."""

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "usage.log"
    _write_router_stub(bin_dir / "local-ai-agent.py", log_path, {})

    result = _run_middleware(["totally-unknown-cli", "--sync"], bin_dir=bin_dir, log_path=log_path)

    assert result.returncode == 1
    assert "Router route: reject" in result.stdout
    assert "no deterministic fix available" in result.stdout


def test_real_usage_complex_arguments_preserve_spaces_and_flag_values(tmp_path: Path) -> None:
    """Paths with spaces and explicit flag values must survive the middleware unchanged."""

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "usage.log"
    command = [
        "broken-tool",
        "--path",
        "C:\\Users\\Max Li\\Documents\\Project Files",
        "--mode",
        "safe",
    ]
    command_text = "broken-tool --path C:\\Users\\Max Li\\Documents\\Project Files --mode safe"
    routes = {
        command_text: {
            "kind": "route",
            "snapshot_version": "snap-test",
            "route": "command_fix",
            "intent": "correction",
            "payload": {
                "original": command_text,
                "suggested_command": 'fixed-tool --path "C:\\Users\\Max Li\\Documents\\Project Files" --mode safe',
            },
            "evidence": ["test:complex_args"],
            "confidence": 1.0,
            "threshold_applied": 0.9,
            "threshold_source": "intent:command_fix",
            "resolver_path": ["test"],
        }
    }
    _write_router_stub(bin_dir / "local-ai-agent.py", log_path, routes)

    result = _run_middleware(command, bin_dir=bin_dir, log_path=log_path)

    assert result.returncode == 0
    calls = _read_log_lines(log_path)
    assert any(command_text in line for line in calls)
    assert "Suggested command:" in result.stdout
