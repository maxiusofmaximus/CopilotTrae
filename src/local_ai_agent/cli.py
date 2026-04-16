from __future__ import annotations

import argparse
import sys
from typing import Sequence, TextIO

from local_ai_agent.config import Settings
from local_ai_agent.runtime import AppRuntime, build_runtime
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
