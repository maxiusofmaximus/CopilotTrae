from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from local_ai_agent.router.classifier import normalize_input, parse_command_shape
from local_ai_agent.router.output import RouteEnvelope


def _normalize_token(value: str) -> str:
    return value.lower().replace(".", "-").replace("_", "-")


@dataclass(frozen=True, slots=True)
class _Candidate:
    tool_name: str
    score: float
    evidence: str


class CommandFixEngine:
    def build_fix(
        self,
        *,
        raw_input: str,
        tools: list[Mapping[str, object]],
        threshold: float,
        snapshot_version: str = "",
        resolver_prefix: list[str] | None = None,
    ) -> RouteEnvelope:
        resolver_path = list(resolver_prefix or [])
        normalized = normalize_input(raw_input)
        command, args = parse_command_shape(normalized)
        normalized_command = _normalize_token(command)

        resolver_path.append("fixes.collect_alias_matches")
        alias_matches = self._collect_alias_matches(normalized_command, tools)
        resolver_path.append("fixes.collect_suffix_matches")
        suffix_matches = self._collect_suffix_matches(normalized_command, tools)
        resolver_path.append("fixes.rank_candidates")

        candidates = self._rank_candidates(alias_matches + suffix_matches)
        if not candidates:
            return RouteEnvelope.clarification(
                intent="correction",
                snapshot_version=snapshot_version,
                original=normalized,
                options=[],
                evidence=["no_fix_candidates"],
                confidence=0.0,
                threshold_applied=threshold,
                threshold_source="intent:command_fix",
                resolver_path=resolver_path,
            )

        top_score = candidates[0].score
        top_candidates = [candidate for candidate in candidates if candidate.score == top_score]
        options = [self._suggested_command(candidate.tool_name, args) for candidate in top_candidates]

        if len(top_candidates) > 1 or top_score < threshold:
            return RouteEnvelope.clarification(
                intent="correction",
                snapshot_version=snapshot_version,
                original=normalized,
                options=options,
                evidence=[candidate.evidence for candidate in top_candidates],
                confidence=top_score,
                threshold_applied=threshold,
                threshold_source="intent:command_fix",
                resolver_path=resolver_path,
            )

        chosen = top_candidates[0]
        return RouteEnvelope.command_fix(
            intent="correction",
            snapshot_version=snapshot_version,
            original=normalized,
            suggested_command=self._suggested_command(chosen.tool_name, args),
            evidence=[chosen.evidence],
            confidence=chosen.score,
            threshold_applied=threshold,
            threshold_source="intent:command_fix",
            resolver_path=resolver_path,
        )

    def _collect_alias_matches(
        self,
        normalized_command: str,
        tools: list[Mapping[str, object]],
    ) -> list[_Candidate]:
        matches: list[_Candidate] = []
        for tool in tools:
            tool_name = str(tool.get("tool_name", ""))
            aliases = tuple(str(alias) for alias in tool.get("aliases", ()))
            if normalized_command == _normalize_token(tool_name):
                matches.append(_Candidate(tool_name=tool_name, score=1.0, evidence=f"tool_name_match:{tool_name}"))
                continue
            for alias in aliases:
                if normalized_command == _normalize_token(alias):
                    matches.append(_Candidate(tool_name=tool_name, score=1.0, evidence=f"alias_match:{alias}"))
                    break
        return matches

    def _collect_suffix_matches(
        self,
        normalized_command: str,
        tools: list[Mapping[str, object]],
    ) -> list[_Candidate]:
        matches: list[_Candidate] = []
        for tool in tools:
            tool_name = str(tool.get("tool_name", ""))
            aliases = tuple(str(alias) for alias in tool.get("aliases", ()))
            normalized_tool_name = _normalize_token(tool_name)
            if normalized_command.endswith(normalized_tool_name) or normalized_tool_name.endswith(normalized_command):
                matches.append(_Candidate(tool_name=tool_name, score=0.9, evidence=f"suffix_match:{tool_name}"))
                continue
            for alias in aliases:
                normalized_alias = _normalize_token(alias)
                if normalized_command.endswith(normalized_alias) or normalized_alias.endswith(normalized_command):
                    matches.append(_Candidate(tool_name=tool_name, score=0.9, evidence=f"suffix_match:{alias}"))
                    break
        return matches

    def _rank_candidates(self, candidates: list[_Candidate]) -> list[_Candidate]:
        best_by_tool: dict[str, _Candidate] = {}
        for candidate in candidates:
            current = best_by_tool.get(candidate.tool_name)
            if current is None or candidate.score > current.score:
                best_by_tool[candidate.tool_name] = candidate
        return sorted(best_by_tool.values(), key=lambda item: (-item.score, item.tool_name))

    def _suggested_command(self, tool_name: str, args: list[str]) -> str:
        if not args:
            return tool_name
        return f"{tool_name} {' '.join(args)}"
