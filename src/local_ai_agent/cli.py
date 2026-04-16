from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence, TextIO

from local_ai_agent.config import Settings
from local_ai_agent.runtime import AppRuntime, build_runtime
from local_ai_agent.router.request import TerminalRequest
from local_ai_agent.session_runner import AgentSessionRunner, ReplyRequest


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
    return parser


def main(
    argv: Sequence[str] | None = None,
    runtime: AppRuntime | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    settings = Settings.from_env()
    if args.command == "route":
        route_runtime = getattr(runtime, "router_runtime", None)
        if route_runtime is None:
            parser.error("The route command requires a runtime with a bound router_runtime.")
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


if __name__ == "__main__":
    raise SystemExit(main())
