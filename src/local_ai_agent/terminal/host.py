from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol
from uuid import uuid4

from local_ai_agent.router.errors import RouterErrorEnvelope
from local_ai_agent.router.output import RouteEnvelope
from local_ai_agent.router.request import TerminalRequest
from local_ai_agent.terminal.executor import CommandExecutor, ExecutionResult

ShellName = Literal["powershell", "bash"]


class SnapshotLike(Protocol):
    snapshot_version: str


class RouterRuntimeLike(Protocol):
    snapshot: SnapshotLike

    def resolve(self, request: TerminalRequest) -> RouteEnvelope | RouterErrorEnvelope:
        ...


ConfirmationPolicy = Callable[[str, RouteEnvelope], bool]


def _default_request_id() -> str:
    return uuid4().hex


def _deny_confirmation(command: str, envelope: RouteEnvelope) -> bool:
    del command, envelope
    return False


@dataclass(slots=True)
class TerminalHostResult:
    route: str
    action: str
    message: str
    request: TerminalRequest
    envelope: RouteEnvelope | RouterErrorEnvelope
    suggested_command: str | None = None
    executed_command: str | None = None
    execution_result: ExecutionResult | object | None = None
    blocked_reason: str | None = None
    options: list[str] = field(default_factory=list)
    can_execute_suggested_command: bool = False
    proposal: dict[str, object] | None = None


class TerminalHost:
    def __init__(
        self,
        *,
        router_runtime: RouterRuntimeLike,
        executor: CommandExecutor,
        session_id: str,
        shell: ShellName,
        cwd: str | None = None,
        request_id_factory: Callable[[], str] | None = None,
        confirmation_policy: ConfirmationPolicy | None = None,
        correction_policy: ConfirmationPolicy | None = None,
    ) -> None:
        self._router_runtime = router_runtime
        self._executor = executor
        self._session_id = session_id
        self._shell = shell
        self._cwd = cwd or str(Path.cwd())
        self._request_id_factory = request_id_factory or _default_request_id
        self._confirmation_policy = confirmation_policy or _deny_confirmation
        self._correction_policy = correction_policy or _deny_confirmation

    def handle_input(self, text: str) -> TerminalHostResult:
        request = self._build_request(text, requested_mode="interactive")
        envelope = self._router_runtime.resolve(request)
        if isinstance(envelope, RouterErrorEnvelope):
            return TerminalHostResult(
                route="router_error",
                action="blocked",
                message=f"Router error: {envelope.error_code}",
                request=request,
                envelope=envelope,
                blocked_reason=envelope.error_code,
            )

        handler = getattr(self, f"_handle_{envelope.route}", self._handle_unknown)
        return handler(request, envelope)

    def preview_input(self, text: str) -> TerminalHostResult:
        request = self._build_request(text, requested_mode="dry_run")
        envelope = self._router_runtime.resolve(request)
        if isinstance(envelope, RouterErrorEnvelope):
            return TerminalHostResult(
                route="router_error",
                action="blocked",
                message=f"Router error: {envelope.error_code}",
                request=request,
                envelope=envelope,
                blocked_reason=envelope.error_code,
            )
        if envelope.route == "tool_execution":
            command = self._command_from_argv(envelope.payload.get("argv"))
            return TerminalHostResult(
                route=envelope.route,
                action="dry_run",
                message=f"Dry-run: would execute command: {command}",
                request=request,
                envelope=envelope,
                executed_command=command,
            )
        handler = getattr(self, f"_handle_{envelope.route}", self._handle_unknown)
        return handler(request, envelope)

    def _build_request(self, text: str, *, requested_mode: str) -> TerminalRequest:
        request = TerminalRequest(
            request_id=self._request_id_factory(),
            session_id=self._session_id,
            shell=self._shell,
            raw_input=text,
            cwd=self._cwd,
            snapshot_version=self._router_runtime.snapshot.snapshot_version,
            requested_mode=requested_mode,
        )
        return request

    def execute_suggested_command(self, result: TerminalHostResult) -> TerminalHostResult:
        suggested_command = (result.suggested_command or "").strip()
        if not suggested_command:
            raise ValueError("No suggested command is available to execute.")
        execution_result = self._executor.execute(suggested_command)
        return TerminalHostResult(
            route=result.route,
            action="executed",
            message=f"Executed suggested command: {suggested_command}",
            request=result.request,
            envelope=result.envelope,
            suggested_command=suggested_command,
            executed_command=suggested_command,
            execution_result=execution_result,
            can_execute_suggested_command=True,
        )

    def render_lines(self, result: TerminalHostResult) -> list[str]:
        if result.action == "suggest_correction":
            lines = ["Command not found.", ""]
            if result.suggested_command:
                lines.extend(["Suggested command:", result.suggested_command, ""])
            return lines
        if result.action == "clarify":
            lines = ["Clarification required.", ""]
            if result.options:
                lines.append("Options:")
                lines.extend(result.options)
            return lines
        if result.action == "blocked":
            return [result.message]
        if result.action == "executed":
            return [result.message]
        if result.action == "needs_ai":
            return [result.message]
        if result.action == "show_proposal":
            return [result.message]
        if result.action == "confirmation_required":
            return [result.message]
        if result.action == "dry_run":
            return [result.message]
        return [result.message]

    def confirmation_prompt(self, result: TerminalHostResult) -> str | None:
        if result.action == "suggest_correction" and result.suggested_command:
            return "Execute suggested command? (y/n): "
        if result.action == "confirmation_required" and result.executed_command:
            return f"Execute command? {result.executed_command} (y/n): "
        return None

    def _handle_tool_execution(
        self,
        request: TerminalRequest,
        envelope: RouteEnvelope,
    ) -> TerminalHostResult:
        execution_policy = envelope.payload.get("execution_policy")
        if isinstance(execution_policy, Mapping) and execution_policy.get("allowed") is False:
            return TerminalHostResult(
                route=envelope.route,
                action="blocked",
                message="Execution blocked by policy.",
                request=request,
                envelope=envelope,
                blocked_reason="execution_policy_denied",
            )

        command = self._command_from_argv(envelope.payload.get("argv"))
        requires_confirmation = bool(envelope.payload.get("requires_confirmation", False))
        if requires_confirmation and not self._confirmation_policy(command, envelope):
            return TerminalHostResult(
                route=envelope.route,
                action="confirmation_required",
                message=f"Confirmation required before executing: {command}",
                request=request,
                envelope=envelope,
                executed_command=command,
            )

        execution_result = self._executor.execute(command)
        return TerminalHostResult(
            route=envelope.route,
            action="executed",
            message=f"Executed command: {command}",
            request=request,
            envelope=envelope,
            executed_command=command,
            execution_result=execution_result,
        )

    def _handle_command_fix(
        self,
        request: TerminalRequest,
        envelope: RouteEnvelope,
    ) -> TerminalHostResult:
        suggested_command = str(envelope.payload.get("suggested_command", "")).strip()
        if suggested_command and self._correction_policy(suggested_command, envelope):
            execution_result = self._executor.execute(suggested_command)
            return TerminalHostResult(
                route=envelope.route,
                action="executed",
                message=f"Executed suggested command: {suggested_command}",
                request=request,
                envelope=envelope,
                suggested_command=suggested_command,
                executed_command=suggested_command,
                execution_result=execution_result,
                can_execute_suggested_command=True,
            )

        return TerminalHostResult(
            route=envelope.route,
            action="suggest_correction",
            message=f"Suggested command: {suggested_command}",
            request=request,
            envelope=envelope,
            suggested_command=suggested_command,
            can_execute_suggested_command=bool(suggested_command),
        )

    def _handle_ai_assist(
        self,
        request: TerminalRequest,
        envelope: RouteEnvelope,
    ) -> TerminalHostResult:
        return TerminalHostResult(
            route=envelope.route,
            action="needs_ai",
            message="This request requires AI assistance.",
            request=request,
            envelope=envelope,
        )

    def _handle_hub_install(
        self,
        request: TerminalRequest,
        envelope: RouteEnvelope,
    ) -> TerminalHostResult:
        return self._proposal_result(request, envelope)

    def _handle_hub_action_proposal(
        self,
        request: TerminalRequest,
        envelope: RouteEnvelope,
    ) -> TerminalHostResult:
        return self._proposal_result(request, envelope)

    def _handle_clarification(
        self,
        request: TerminalRequest,
        envelope: RouteEnvelope,
    ) -> TerminalHostResult:
        options = [str(item) for item in envelope.payload.get("options", [])]
        return TerminalHostResult(
            route=envelope.route,
            action="clarify",
            message="Clarification required. Options: " + ", ".join(options),
            request=request,
            envelope=envelope,
            options=options,
        )

    def _handle_reject(
        self,
        request: TerminalRequest,
        envelope: RouteEnvelope,
    ) -> TerminalHostResult:
        return self._blocked_result(request, envelope)

    def _handle_policy_denied(
        self,
        request: TerminalRequest,
        envelope: RouteEnvelope,
    ) -> TerminalHostResult:
        return self._blocked_result(request, envelope)

    def _handle_unknown(
        self,
        request: TerminalRequest,
        envelope: RouteEnvelope,
    ) -> TerminalHostResult:
        return TerminalHostResult(
            route=envelope.route,
            action="blocked",
            message=f"Unsupported route: {envelope.route}",
            request=request,
            envelope=envelope,
            blocked_reason=f"unsupported:{envelope.route}",
        )

    def _proposal_result(
        self,
        request: TerminalRequest,
        envelope: RouteEnvelope,
    ) -> TerminalHostResult:
        proposal = envelope.payload.get("proposal")
        proposal_dict = dict(proposal) if isinstance(proposal, Mapping) else {}
        return TerminalHostResult(
            route=envelope.route,
            action="show_proposal",
            message=f"Hub proposal available: {proposal_dict}",
            request=request,
            envelope=envelope,
            proposal=proposal_dict,
        )

    def _blocked_result(
        self,
        request: TerminalRequest,
        envelope: RouteEnvelope,
    ) -> TerminalHostResult:
        reason = str(envelope.payload.get("reason", "blocked"))
        return TerminalHostResult(
            route=envelope.route,
            action="blocked",
            message=f"Execution blocked: {reason}",
            request=request,
            envelope=envelope,
            blocked_reason=reason,
        )

    @staticmethod
    def _command_from_argv(argv: object) -> str:
        if not isinstance(argv, list):
            return ""
        return " ".join(str(item) for item in argv)
