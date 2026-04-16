from __future__ import annotations

from local_ai_agent.router.classifier import normalize_input, parse_command_shape
from local_ai_agent.router.errors import RouterErrorEnvelope
from local_ai_agent.router.fixes import CommandFixEngine
from local_ai_agent.router.output import RouteEnvelope
from local_ai_agent.router.policies import ConfidencePolicy
from local_ai_agent.router.request import TerminalRequest
from local_ai_agent.router.snapshot import RegistrySnapshot


class DeterministicRouter:
    def __init__(
        self,
        *,
        confidence_policy: ConfidencePolicy | None = None,
        fix_engine: CommandFixEngine | None = None,
    ) -> None:
        self._confidence_policy = confidence_policy or ConfidencePolicy.defaults()
        self._fix_engine = fix_engine or CommandFixEngine()

    def resolve(
        self,
        request: TerminalRequest,
        snapshot: RegistrySnapshot,
    ) -> RouteEnvelope | RouterErrorEnvelope:
        if request.snapshot_version != snapshot.snapshot_version:
            return RouterErrorEnvelope(
                error_code="snapshot_version_mismatch",
                request_id=request.request_id,
                session_id=request.session_id,
                snapshot_version=snapshot.snapshot_version,
                diagnostics={
                    "request_snapshot_version": request.snapshot_version,
                    "active_snapshot_version": snapshot.snapshot_version,
                },
            )

        resolver_path: list[str] = []
        normalized = normalize_input(request.raw_input)
        resolver_path.append("normalize_input")
        command, args = parse_command_shape(normalized)
        resolver_path.append("parse_command_shape")

        resolver_path.append("classify_intent")
        tools = list(snapshot.execution_surface.get("tools", ()))
        resolver_path.append("resolve_local_candidates")
        matching_tool = next(
            (tool for tool in tools if tool.get("tool_name") == command and tool.get("available") is True),
            None,
        )

        resolver_path.append("apply_deterministic_rules")
        if matching_tool is None:
            result = self._fix_engine.build_fix(
                raw_input=normalized,
                tools=tools,
                threshold=self._confidence_policy.for_intent("command_fix"),
                snapshot_version=snapshot.snapshot_version,
                resolver_prefix=resolver_path,
            )
            result.resolver_path.append("evaluate_confidence")
            return result

        resolver_path.append("evaluate_confidence")
        return RouteEnvelope.tool_execution(
            intent="tool_execution",
            snapshot_version=snapshot.snapshot_version,
            tool_name=str(matching_tool["tool_name"]),
            shell=str(matching_tool.get("shell", request.shell)),
            argv=[command, *args],
            confidence=1.0,
            threshold_applied=0.93,
            threshold_source="intent:execution",
            resolver_path=resolver_path,
            evidence=[f"tool_name_match:{command}"],
        )
