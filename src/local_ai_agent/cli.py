from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence, TextIO

from local_ai_agent.config import Settings
from local_ai_agent.runtime import AppRuntime, build_router_runtime, build_runtime
from local_ai_agent.router.request import TerminalRequest
from local_ai_agent.session_runner import AgentSessionRunner, ReplyRequest, serialize_router_envelope
from local_ai_agent.terminal.executor import CommandExecutor, ExecutionResult
from local_ai_agent.terminal.host import TerminalHost, TerminalHostResult


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="local-ai-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    reply = subparsers.add_parser("reply", help="Generate a single reply from text, stdin, or a file.")
    reply.add_argument("--text", help="Inline text to process.")
    reply.add_argument("--input-file", help="Read input from a UTF-8 text file.")
    reply.add_argument("--copy", action="store_true", help="Offer to copy the generated response.")
    reply.add_argument("--show-memory", action="store_true", help="Show current memory snapshot after the reply.")

    chat = subparsers.add_parser("chat", help="Run an interactive multi-turn session.")
    chat.add_argument("--copy", action="store_true", help="Offer to copy each generated response.")
    chat.add_argument("--show-memory", action="store_true", help="Show memory snapshot after each turn.")

    route = subparsers.add_parser("route", help="Resolve terminal input into a JSON routing decision.")
    route.add_argument("--text", required=True, help="Raw terminal input to route.")
    route.add_argument("--shell", choices=["powershell", "bash"], required=True, help="Shell surface for command parsing.")
    route.add_argument("--cwd", required=True, help="Current working directory for routing context.")
    route.add_argument("--snapshot-version", required=True, help="Bound registry snapshot version to resolve against.")
    route.add_argument("--request-id", help="Optional request identifier override.")
    route.add_argument("--session-id", help="Optional session identifier override.")

    exec_parser = subparsers.add_parser("exec", help="Route and execute one terminal command through the terminal host.")
    exec_parser.add_argument("--yes", action="store_true", help="Auto-confirm suggested command execution.")
    exec_parser.add_argument("--dry-run", action="store_true", help="Never execute; only show routing decisions.")
    exec_parser.add_argument("--json", action="store_true", help="Print only the serialized RouteEnvelope.")
    exec_parser.add_argument("--debug", action="store_true", help="Write route and host debug details to stderr.")
    exec_parser.add_argument("--shell", choices=["powershell", "bash"], default=_default_shell(), help="Shell surface for command parsing.")
    exec_parser.add_argument("--cwd", default=str(Path.cwd()), help="Current working directory for routing context.")
    exec_parser.add_argument("text", nargs=argparse.REMAINDER, help="Command text to route and execute.")

    terminal = subparsers.add_parser("terminal", help="Run an interactive terminal middleware loop.")
    terminal.add_argument("--shell", choices=["powershell", "bash"], default=_default_shell(), help="Shell surface for command parsing.")
    terminal.add_argument("--cwd", default=str(Path.cwd()), help="Current working directory for routing context.")
    return parser


def main(
    argv: Sequence[str] | None = None,
    runtime: AppRuntime | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = build_parser()
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    normalized_argv = _normalize_exec_argv(raw_argv)
    args = parser.parse_args(normalized_argv)
    settings = Settings.from_env()
    if args.command in {"route", "exec", "terminal"}:
        route_runtime = getattr(runtime, "router_runtime", None)
        if route_runtime is None:
            route_runtime = build_router_runtime(settings, shell=args.shell)
    if args.command == "route":
        request = TerminalRequest(
            request_id=args.request_id or f"route-{settings.session_id}",
            session_id=args.session_id or settings.session_id,
            shell=args.shell,
            raw_input=args.text,
            cwd=args.cwd,
            snapshot_version=args.snapshot_version,
        )
        payload = route_runtime.resolve_serialized(request)
        stdout.write(json.dumps(payload, ensure_ascii=True))
        return 0
    if args.command == "exec":
        command_text = _command_text(args.text, parser)
        if args.json:
            request = _build_terminal_request(
                settings=settings,
                shell=args.shell,
                cwd=args.cwd,
                text=command_text,
                snapshot_version=route_runtime.snapshot.snapshot_version,
                request_prefix="exec-json",
                requested_mode="json",
            )
            envelope = route_runtime.resolve(request)
            payload = serialize_router_envelope(envelope)
            if args.debug:
                _emit_debug(stderr=stderr, envelope=envelope, host_action="json_output")
            stdout.write(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.dry_run:
            return _exec_dry_run(
                route_runtime=route_runtime,
                settings=settings,
                shell=args.shell,
                cwd=args.cwd,
                text=command_text,
                stdout=stdout,
                stderr=stderr,
                debug=args.debug,
            )
        host = _build_terminal_host(
            route_runtime=route_runtime,
            settings=settings,
            shell=args.shell,
            cwd=args.cwd,
            stdin=stdin,
            stdout=stdout,
        )
        result = host.handle_input(command_text)
        if args.debug:
            _emit_debug(stderr=stderr, envelope=result.envelope, host_action=result.action)
        return _render_terminal_result(result=result, host=host, stdin=stdin, stdout=stdout, auto_confirm=args.yes)
    if args.command == "terminal":
        host = _build_terminal_host(
            route_runtime=route_runtime,
            settings=settings,
            shell=args.shell,
            cwd=args.cwd,
            stdin=stdin,
            stdout=stdout,
        )
        return _run_terminal_loop(host=host, stdin=stdin, stdout=stdout)

    runtime = runtime or build_runtime(settings, stdin=stdin, stdout=stdout)

    try:
        if args.command == "reply":
            result = runtime.runner.run_reply(
                ReplyRequest(
                    text=args.text,
                    input_file=args.input_file,
                    copy_response=args.copy,
                    show_memory=args.show_memory,
                )
            )
            return result.exit_code
        if args.command == "chat":
            return runtime.runner.run_chat(show_memory=args.show_memory, copy_response=args.copy)
    except KeyboardInterrupt:
        runtime.output.emit("Interrupted. Exiting safely.")
        return 130

    parser.error(f"Unknown command: {args.command}")
    return 2


def _default_shell() -> str:
    return "powershell" if os.name == "nt" else "bash"


def _normalize_exec_argv(argv: Sequence[str] | None) -> list[str] | None:
    if argv is None:
        return None
    items = list(argv)
    if not items or items[0] != "exec":
        return items
    trailing_flags: list[str] = []
    while len(items) > 1 and items[-1] in {"--yes", "--dry-run", "--json", "--debug"}:
        trailing_flags.insert(0, items.pop())
    return [items[0], *trailing_flags, *items[1:]]


def _command_text(parts: Sequence[str], parser: argparse.ArgumentParser) -> str:
    text = " ".join(parts).strip()
    if not text:
        parser.error("The exec command requires command text.")
    return text


def _build_terminal_host(
    *,
    route_runtime: object,
    settings: Settings,
    shell: str,
    cwd: str,
    stdin: TextIO,
    stdout: TextIO,
) -> TerminalHost:
    return TerminalHost(
        router_runtime=route_runtime,
        executor=CommandExecutor(),
        session_id=settings.session_id,
        shell=shell,
        cwd=cwd,
        confirmation_policy=lambda command, envelope: _confirm(
            prompt=f"Execute command? {command} (y/n) ",
            stdin=stdin,
            stdout=stdout,
        ),
    )


def _build_terminal_request(
    *,
    settings: Settings,
    shell: str,
    cwd: str,
    text: str,
    snapshot_version: str,
    request_prefix: str,
    requested_mode: str,
) -> TerminalRequest:
    return TerminalRequest(
        request_id=f"{request_prefix}-{settings.session_id}",
        session_id=settings.session_id,
        shell=shell,
        raw_input=text,
        cwd=cwd,
        snapshot_version=snapshot_version,
        requested_mode=requested_mode,
    )


def _exec_dry_run(
    *,
    route_runtime: object,
    settings: Settings,
    shell: str,
    cwd: str,
    text: str,
    stdout: TextIO,
    stderr: TextIO,
    debug: bool,
) -> int:
    host = TerminalHost(
        router_runtime=route_runtime,
        executor=CommandExecutor(),
        session_id=settings.session_id,
        shell=shell,
        cwd=cwd,
    )
    result = host.preview_input(text)
    if debug:
        _emit_debug(stderr=stderr, envelope=result.envelope, host_action=result.action)
    for line in host.render_lines(result):
        _write_line(stdout, line)
    _write_line(stdout, "")
    _write_line(stdout, "Dry-run: no commands executed.")
    return 0


def _emit_debug(*, stderr: TextIO, envelope: object, host_action: str) -> None:
    payload = serialize_router_envelope(envelope)
    route = payload.get("route", "router_error")
    _write_line(stderr, f"[debug] route={route}")
    _write_line(stderr, f"[debug] host_action={host_action}")
    _write_line(stderr, f"[debug] envelope={json.dumps(payload, ensure_ascii=True)}")


def _run_terminal_loop(
    *,
    host: TerminalHost,
    stdin: TextIO,
    stdout: TextIO,
) -> int:
    exit_code = 0
    while True:
        raw_text = _read_line("terminal> ", stdin=stdin, stdout=stdout)
        if raw_text == "":
            return exit_code
        text = raw_text.strip()
        if not text:
            continue
        if text.lower() in {"exit", "quit"}:
            return exit_code
        result = host.handle_input(text)
        exit_code = _render_terminal_result(result=result, host=host, stdin=stdin, stdout=stdout)


def _render_terminal_result(
    *,
    result: TerminalHostResult,
    host: TerminalHost,
    stdin: TextIO,
    stdout: TextIO,
    auto_confirm: bool = False,
) -> int:
    for line in host.render_lines(result):
        _write_line(stdout, line)
    if result.action == "executed":
        return _emit_execution_result(result.execution_result, stdout)
    if result.action == "suggest_correction":
        if result.suggested_command:
            should_execute = auto_confirm
            if not should_execute:
                prompt = host.confirmation_prompt(result) or "Execute suggested command? (y/n): "
                should_execute = _confirm(
                    prompt=prompt,
                    stdin=stdin,
                    stdout=stdout,
                )
            if should_execute:
                executed = host.execute_suggested_command(result)
                for line in host.render_lines(executed):
                    _write_line(stdout, line)
                return _emit_execution_result(executed.execution_result, stdout)
        return 0
    if result.action in {"blocked", "clarify", "confirmation_required", "needs_ai", "show_proposal"}:
        return 1 if result.action in {"blocked", "clarify", "needs_ai", "show_proposal"} else 0
    return 1


def _emit_execution_result(result: object, stdout: TextIO) -> int:
    if not isinstance(result, ExecutionResult):
        return 0
    if result.stdout.strip():
        _write_line(stdout, result.stdout.strip())
    if result.stderr.strip():
        _write_line(stdout, result.stderr.strip())
    return result.returncode


def _confirm(*, prompt: str, stdin: TextIO, stdout: TextIO) -> bool:
    answer = _read_line(prompt, stdin=stdin, stdout=stdout).strip().lower()
    return answer in {"y", "yes"}


def _read_line(prompt: str, *, stdin: TextIO, stdout: TextIO) -> str:
    if stdin is sys.stdin and stdout is sys.stdout:
        try:
            return input(prompt)
        except EOFError:
            return ""
    stdout.write(prompt)
    stdout.flush()
    return stdin.readline()


def _write_line(stdout: TextIO, text: str) -> None:
    stdout.write(text.rstrip() + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
