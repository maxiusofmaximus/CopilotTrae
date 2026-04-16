from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EnvelopeMetadata:
    kind: str
    snapshot_version: str


@dataclass(slots=True)
class RouteEnvelope:
    envelope: EnvelopeMetadata
    route: str
    intent: str
    payload: dict[str, Any]
    evidence: list[str]
    confidence: float
    threshold_applied: float
    threshold_source: str
    resolver_path: list[str]

    @property
    def kind(self) -> str:
        return self.envelope.kind

    @property
    def snapshot_version(self) -> str:
        return self.envelope.snapshot_version

    @classmethod
    def command_fix(
        cls,
        *,
        intent: str,
        snapshot_version: str,
        original: str,
        suggested_command: str,
        evidence: list[str],
        confidence: float,
        threshold_applied: float,
        threshold_source: str,
        resolver_path: list[str],
    ) -> "RouteEnvelope":
        return cls(
            envelope=EnvelopeMetadata(kind="route", snapshot_version=snapshot_version),
            route="command_fix",
            intent=intent,
            payload={
                "original": original,
                "suggested_command": suggested_command,
            },
            evidence=evidence,
            confidence=confidence,
            threshold_applied=threshold_applied,
            threshold_source=threshold_source,
            resolver_path=resolver_path,
        )

    @classmethod
    def tool_execution(
        cls,
        *,
        intent: str,
        snapshot_version: str,
        tool_name: str,
        shell: str,
        argv: list[str],
        confidence: float,
        threshold_applied: float,
        threshold_source: str,
        resolver_path: list[str],
        evidence: list[str],
    ) -> "RouteEnvelope":
        return cls(
            envelope=EnvelopeMetadata(kind="route", snapshot_version=snapshot_version),
            route="tool_execution",
            intent=intent,
            payload={
                "tool_name": tool_name,
                "shell": shell,
                "argv": argv,
            },
            evidence=evidence,
            confidence=confidence,
            threshold_applied=threshold_applied,
            threshold_source=threshold_source,
            resolver_path=resolver_path,
        )

    @classmethod
    def clarification(
        cls,
        *,
        intent: str,
        snapshot_version: str,
        original: str,
        options: list[str],
        evidence: list[str],
        confidence: float,
        threshold_applied: float,
        threshold_source: str,
        resolver_path: list[str],
    ) -> "RouteEnvelope":
        return cls(
            envelope=EnvelopeMetadata(kind="route", snapshot_version=snapshot_version),
            route="clarification",
            intent=intent,
            payload={
                "original": original,
                "options": options,
            },
            evidence=evidence,
            confidence=confidence,
            threshold_applied=threshold_applied,
            threshold_source=threshold_source,
            resolver_path=resolver_path,
        )
