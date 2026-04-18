from __future__ import annotations

import pytest

from local_ai_agent.hub.credentials_contracts import (
    CredentialDescriptor,
    CredentialSourceKind,
    CredentialState,
    CredentialStatus,
    CredentialWriteResult,
    SecretValue,
)


class SpySink:
    def __init__(self) -> None:
        self.accepted: list[str] = []

    def accept_secret(self, secret: str) -> None:
        self.accepted.append(secret)


def test_secret_value_redacts_string_representations() -> None:
    secret = SecretValue("abc-123")

    assert str(secret) == "[REDACTED]"
    assert repr(secret) == "[REDACTED]"


def test_secret_value_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        SecretValue("   ")


def test_secret_value_only_writes_through_sink() -> None:
    secret = SecretValue("abc-123")
    sink = SpySink()

    secret.write_into(sink)

    assert sink.accepted == ["abc-123"]


def test_credential_metadata_types_carry_only_safe_fields() -> None:
    descriptor = CredentialDescriptor(
        provider_id="cerebras",
        label="Cerebras",
        expected_env_vars=("LOCAL_AI_AGENT_API_KEY", "CEREBRAS_API_KEY"),
        supports_fallback=False,
    )
    status = CredentialStatus(
        provider_id="cerebras",
        state=CredentialState.CONFIGURED,
        source_kind=CredentialSourceKind.ENV,
        has_secret=True,
        missing_fields=(),
        safe_summary="configured from env",
    )
    result = CredentialWriteResult(
        provider_id="cerebras",
        source_kind=CredentialSourceKind.ENV,
        scope="process",
        changed_keys=("LOCAL_AI_AGENT_API_KEY",),
    )

    assert descriptor.provider_id == "cerebras"
    assert status.safe_summary == "configured from env"
    assert result.changed_keys == ("LOCAL_AI_AGENT_API_KEY",)
