from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MIDDLEWARE_PATH = REPO_ROOT / "scripts" / "powershell" / "middleware.ps1"


def _write_cmd(path: Path, body: str) -> None:
    path.write_text("@echo off\r\n" + body.strip() + "\r\n", encoding="utf-8")


def _run_middleware(
    command: list[str],
    *,
    bin_dir: Path,
    log_path: Path,
    stdin_text: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["MIDDLEWARE_LOG"] = str(log_path)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(MIDDLEWARE_PATH), *command],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        input=stdin_text,
        check=False,
    )


def _read_log_lines(log_path: Path) -> list[str]:
    if not log_path.exists():
        return []
    return log_path.read_text(encoding="utf-8").splitlines()


def test_middleware_falls_back_on_non_zero_exit_and_routes_before_exec(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "middleware.log"

    _write_cmd(
        bin_dir / "local-ai-agent.cmd",
        r"""
if /I "%~1"=="exec" if /I "%~2"=="--json" (
  >>"%MIDDLEWARE_LOG%" echo json %*
  echo {"kind":"route","snapshot_version":"snap-test","route":"command_fix","intent":"correction","payload":{"original":"broken-tool --version","suggested_command":"gh --version"},"evidence":[],"confidence":1.0,"threshold_applied":0.9,"threshold_source":"intent:command_fix","resolver_path":["test"]}
  exit /b 0
)
if /I "%~1"=="exec" (
  >>"%MIDDLEWARE_LOG%" echo exec %*
  echo fallback-exec-ran
  exit /b 0
)
>>"%MIDDLEWARE_LOG%" echo direct %*
exit /b 9
""",
    )
    _write_cmd(
        bin_dir / "broken-tool.cmd",
        r"""
echo broken-tool-failed 1>&2
exit /b 7
""",
    )

    result = _run_middleware(["broken-tool", "--version"], bin_dir=bin_dir, log_path=log_path)

    assert result.returncode == 0
    assert "fallback-exec-ran" in result.stdout
    calls = _read_log_lines(log_path)
    assert len(calls) == 2
    assert calls[0].startswith("json exec --json --shell powershell --cwd ")
    assert "broken-tool --version" in calls[0]
    assert "--snapshot-version" not in calls[0]
    assert calls[1] == "exec exec --shell powershell --cwd " + str(REPO_ROOT) + " broken-tool --version"


def test_middleware_does_not_fallback_when_local_ai_agent_itself_fails(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "middleware.log"

    _write_cmd(
        bin_dir / "local-ai-agent.cmd",
        r"""
>>"%MIDDLEWARE_LOG%" echo %*
if /I "%~1"=="route" (
  echo unexpected-route
  exit /b 90
)
if /I "%~1"=="exec" (
  echo unexpected-exec
  exit /b 91
)
echo direct-local-ai-agent-failure 1>&2
exit /b 5
""",
    )

    result = _run_middleware(["local-ai-agent", "explode"], bin_dir=bin_dir, log_path=log_path)

    assert result.returncode == 5
    assert result.stdout == ""
    assert "direct-local-ai-agent-failure" in result.stderr
    assert _read_log_lines(log_path) == ["explode"]


def test_middleware_passes_successful_command_output_through_unchanged(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "middleware.log"

    _write_cmd(
        bin_dir / "local-ai-agent.cmd",
        r"""
>>"%MIDDLEWARE_LOG%" echo unexpected %*
exit /b 99
""",
    )
    _write_cmd(
        bin_dir / "ok-tool.cmd",
        r"""
echo alpha
echo beta
exit /b 0
""",
    )

    result = _run_middleware(["ok-tool"], bin_dir=bin_dir, log_path=log_path)

    assert result.returncode == 0
    assert result.stdout == "alpha\nbeta\n"
    assert result.stderr == ""
    assert _read_log_lines(log_path) == []


def test_middleware_falls_back_when_command_is_not_found(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "middleware.log"

    _write_cmd(
        bin_dir / "local-ai-agent.cmd",
        r"""
if /I "%~1"=="exec" if /I "%~2"=="--json" (
  >>"%MIDDLEWARE_LOG%" echo json %*
  echo {"kind":"route","snapshot_version":"snap-test","route":"command_fix","intent":"correction","payload":{"original":"missing-tool --version","suggested_command":"gh --version"},"evidence":[],"confidence":1.0,"threshold_applied":0.9,"threshold_source":"intent:command_fix","resolver_path":["test"]}
  exit /b 0
)
if /I "%~1"=="exec" (
  >>"%MIDDLEWARE_LOG%" echo exec %*
  echo fallback-exec-ran
  exit /b 0
)
exit /b 9
""",
    )

    result = _run_middleware(["missing-tool", "--version"], bin_dir=bin_dir, log_path=log_path)

    assert result.returncode == 0
    assert "fallback-exec-ran" in result.stdout
    calls = _read_log_lines(log_path)
    assert len(calls) == 2
    assert calls[0].startswith("json exec --json --shell powershell --cwd ")
    assert "missing-tool --version" in calls[0]
    assert calls[1] == "exec exec --shell powershell --cwd " + str(REPO_ROOT) + " missing-tool --version"


def test_middleware_refuses_recursive_self_invocation(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "middleware.log"

    _write_cmd(
        bin_dir / "local-ai-agent.cmd",
        r"""
>>"%MIDDLEWARE_LOG%" echo unexpected %*
exit /b 99
""",
    )

    result = _run_middleware([str(MIDDLEWARE_PATH)], bin_dir=bin_dir, log_path=log_path)

    assert result.returncode == 1
    assert "recursive middleware invocation" in result.stderr.lower()
    assert _read_log_lines(log_path) == []


def test_middleware_bypasses_local_ai_agent_when_disabled_even_on_command_failure(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "middleware.log"

    _write_cmd(
        bin_dir / "local-ai-agent.cmd",
        r"""
>>"%MIDDLEWARE_LOG%" echo unexpected %*
exit /b 99
""",
    )
    _write_cmd(
        bin_dir / "broken-tool.cmd",
        r"""
echo broken-tool-failed 1>&2
exit /b 7
""",
    )

    result = _run_middleware(
        ["broken-tool", "--version"],
        bin_dir=bin_dir,
        log_path=log_path,
        extra_env={"LOCAL_AI_AGENT_MIDDLEWARE_DISABLED": "1"},
    )

    assert result.returncode == 7
    assert result.stdout == ""
    assert "broken-tool-failed" in result.stderr
    assert _read_log_lines(log_path) == []


def test_middleware_disabled_mode_still_refuses_recursive_self_invocation(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "middleware.log"

    _write_cmd(
        bin_dir / "local-ai-agent.cmd",
        r"""
>>"%MIDDLEWARE_LOG%" echo unexpected %*
exit /b 99
""",
    )

    result = _run_middleware(
        [str(MIDDLEWARE_PATH)],
        bin_dir=bin_dir,
        log_path=log_path,
        extra_env={"LOCAL_AI_AGENT_MIDDLEWARE_DISABLED": "1"},
    )

    assert result.returncode == 1
    assert "recursive middleware invocation" in result.stderr.lower()
    assert _read_log_lines(log_path) == []


def test_middleware_end_to_end_uses_build_runtime_and_persists_router_events(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "middleware.log"
    logs_dir = tmp_path / "logs"
    driver_path = tmp_path / "local_ai_agent_driver.py"

    driver_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "import sys",
                f"sys.path.insert(0, {str(REPO_ROOT / 'src')!r})",
                "",
                "from local_ai_agent.cli import main",
                "from local_ai_agent.config import Settings",
                "from local_ai_agent.runtime import build_runtime",
                "import local_ai_agent.runtime as runtime_module",
                "",
                "runtime_module.build_multimodal_input_processor = lambda settings: object()",
                "settings = Settings.from_env()",
                "runtime = build_runtime(settings, stdin=sys.stdin, stdout=sys.stdout)",
                "raise SystemExit(main(sys.argv[1:], runtime=runtime, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr))",
            ]
        ),
        encoding="utf-8",
    )
    _write_cmd(
        bin_dir / "local-ai-agent.cmd",
        f'"{sys.executable}" "{driver_path}" %*' + "\r\nexit /b %ERRORLEVEL%",
    )
    _write_cmd(
        bin_dir / "gh.cmd",
        r"""
echo gh version 9.9.9
exit /b 0
""",
    )

    result = _run_middleware(
        ["github.cli", "--version"],
        bin_dir=bin_dir,
        log_path=log_path,
        stdin_text="y\n",
        extra_env={
            "LOCAL_AI_AGENT_PROVIDER": "stub",
            "LOCAL_AI_AGENT_SESSION_ID": "sess-e2e",
            "LOCAL_AI_AGENT_LOGS_DIR": str(logs_dir),
            "LOCAL_AI_AGENT_CONFIRM_BEFORE_COPY": "false",
        },
    )

    assert result.returncode == 0
    assert "Router route: command_fix" in result.stdout
    assert "Suggested command:" in result.stdout
    assert "Executed suggested command: gh --version" in result.stdout
    assert "gh version 9.9.9" in result.stdout

    router_log = logs_dir / "router" / "sess-e2e.jsonl"
    assert router_log.exists()
    lines = router_log.read_text(encoding="utf-8").splitlines()
    assert any('"event_name": "router.request_received"' in line for line in lines)
    assert any('"event_name": "router.route_emitted"' in line for line in lines)
