from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MIDDLEWARE_PATH = REPO_ROOT / "scripts" / "powershell" / "middleware.ps1"


def _write_cmd(path: Path, body: str) -> None:
    path.write_text("@echo off\r\n" + body.strip() + "\r\n", encoding="utf-8")


def _run_middleware(command: list[str], *, bin_dir: Path, log_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["MIDDLEWARE_LOG"] = str(log_path)
    return subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(MIDDLEWARE_PATH), *command],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
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
if /I "%~1"=="route" (
  >>"%MIDDLEWARE_LOG%" echo route %*
  echo {"kind":"route","snapshot_version":"generated","route":"command_fix","intent":"correction","payload":{"original":"broken-tool --version","suggested_command":"gh --version"},"evidence":[],"confidence":1.0,"threshold_applied":0.9,"threshold_source":"intent:command_fix","resolver_path":["test"]} 
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
    assert calls[0].startswith("route route --text ")
    assert "broken-tool --version" in calls[0]
    assert calls[0].endswith(" --shell powershell --cwd " + str(REPO_ROOT) + " --snapshot-version generated")
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
if /I "%~1"=="route" (
  >>"%MIDDLEWARE_LOG%" echo route %*
  echo {"kind":"route","snapshot_version":"generated","route":"command_fix","intent":"correction","payload":{"original":"missing-tool --version","suggested_command":"gh --version"},"evidence":[],"confidence":1.0,"threshold_applied":0.9,"threshold_source":"intent:command_fix","resolver_path":["test"]} 
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
    assert calls[0].startswith("route route --text ")
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
