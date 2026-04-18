from __future__ import annotations

import pytest

from local_ai_agent.hub.credentials_contracts import (
    CredentialDescriptor,
    CredentialScope,
    CredentialSourceKind,
    CredentialState,
    CredentialStatus,
    CredentialWriteResult,
    SecretValue,
)
from local_ai_agent.hub.credential_service import (
    HubCredentialService,
    SecretValidationError,
)
from local_ai_agent.hub.env_credentials import EnvCredentialBackend


class FakeBackend:
    def __init__(
        self,
        descriptors: tuple[CredentialDescriptor, ...],
        statuses: dict[str, CredentialStatus],
        launch_env: dict[str, str] | None = None,
    ) -> None:
        self._descriptors = descriptors
        self._statuses = statuses
        self._launch_env = launch_env or {}
        self.build_launch_env_calls: list[tuple[dict[str, str], str]] = []
        self.received_secrets: list[SecretValue] = []

    def list_descriptors(self) -> tuple[CredentialDescriptor, ...]:
        return self._descriptors

    def get_status(self, provider_id: str) -> CredentialStatus:
        return self._statuses[provider_id]

    def set_secret(
        self,
        provider_id: str,
        secret: SecretValue,
        scope: CredentialScope,
    ) -> CredentialWriteResult:
        self.received_secrets.append(secret)
        return CredentialWriteResult(
            provider_id=provider_id,
            source_kind=CredentialSourceKind.ENV,
            scope=scope,
            changed_keys=("LOCAL_AI_AGENT_API_KEY",),
        )

    def clear_secret(
        self,
        provider_id: str,
        scope: CredentialScope,
    ) -> CredentialWriteResult:
        return CredentialWriteResult(
            provider_id=provider_id,
            source_kind=CredentialSourceKind.ENV,
            scope=scope,
            changed_keys=("LOCAL_AI_AGENT_API_KEY",),
        )

    def build_launch_env(
        self,
        base_env: dict[str, str],
        provider_id: str,
    ) -> dict[str, str]:
        self.build_launch_env_calls.append((dict(base_env), provider_id))
        return {**base_env, **self._launch_env}


def test_service_lists_credentials_from_backend() -> None:
    backend = EnvCredentialBackend(process_env={})
    service = HubCredentialService(backend)

    descriptors = {item.provider_id: item for item in service.list_credentials()}

    assert set(descriptors) == {"cerebras", "openai_compatible", "fallback"}


def test_validate_provider_setup_is_implemented_in_service_not_backend() -> None:
    backend = EnvCredentialBackend(process_env={"LOCAL_AI_AGENT_API_KEY": "test-key"})
    service = HubCredentialService(backend)

    assert not hasattr(backend, "validate_provider_setup")
    assert hasattr(service, "validate_provider_setup")
    assert service.validate_provider_setup("cerebras").state is CredentialState.CONFIGURED


@pytest.mark.parametrize(
    ("process_env",),
    [
        ({"LOCAL_AI_AGENT_API_KEY": "test-key"},),
        ({"CEREBRAS_API_KEY": "test-key"},),
    ],
)
def test_service_validate_provider_setup_accepts_either_cerebras_env_var(
    process_env: dict[str, str],
) -> None:
    backend = EnvCredentialBackend(process_env=process_env)
    service = HubCredentialService(backend)

    status = service.validate_provider_setup("cerebras")

    assert status.state is CredentialState.CONFIGURED
    assert status.has_secret is True
    assert status.missing_fields == ()


def test_service_validate_provider_setup_requires_fallback_key() -> None:
    backend = EnvCredentialBackend(process_env={})
    service = HubCredentialService(backend)

    status = service.validate_provider_setup("fallback")

    assert status.state is CredentialState.MISSING
    assert status.has_secret is False
    assert status.missing_fields == ("LOCAL_AI_AGENT_FALLBACK_API_KEY",)


def test_service_build_launch_env_delegates_to_backend() -> None:
    descriptor = CredentialDescriptor(
        provider_id="cerebras",
        label="Cerebras",
        expected_env_vars=("LOCAL_AI_AGENT_API_KEY", "CEREBRAS_API_KEY"),
        supports_fallback=False,
        write_env_var="LOCAL_AI_AGENT_API_KEY",
    )
    status = CredentialStatus(
        provider_id="cerebras",
        state=CredentialState.CONFIGURED,
        source_kind=CredentialSourceKind.ENV,
        has_secret=True,
        missing_fields=(),
        safe_summary="configured from env",
    )
    backend = FakeBackend(
        descriptors=(descriptor,),
        statuses={"cerebras": status},
        launch_env={"LOCAL_AI_AGENT_API_KEY": "test-key"},
    )
    service = HubCredentialService(backend)

    launch_env = service.build_launch_env({"LOCAL_AI_AGENT_PROVIDER": "cerebras"}, "cerebras")

    assert backend.build_launch_env_calls == [({"LOCAL_AI_AGENT_PROVIDER": "cerebras"}, "cerebras")]
    assert launch_env["LOCAL_AI_AGENT_API_KEY"] == "test-key"


def test_service_set_secret_returns_safe_metadata_without_leaking_secret_value() -> None:
    descriptor = CredentialDescriptor(
        provider_id="cerebras",
        label="Cerebras",
        expected_env_vars=("LOCAL_AI_AGENT_API_KEY", "CEREBRAS_API_KEY"),
        supports_fallback=False,
        write_env_var="LOCAL_AI_AGENT_API_KEY",
    )
    status = CredentialStatus(
        provider_id="cerebras",
        state=CredentialState.MISSING,
        source_kind=CredentialSourceKind.ENV,
        has_secret=False,
        missing_fields=("LOCAL_AI_AGENT_API_KEY", "CEREBRAS_API_KEY"),
        safe_summary="missing env secret",
    )
    backend = FakeBackend(descriptors=(descriptor,), statuses={"cerebras": status})
    service = HubCredentialService(backend)

    result = service.set_secret("cerebras", "super-secret-value", CredentialScope.PROCESS)

    assert result.changed_keys == ("LOCAL_AI_AGENT_API_KEY",)
    assert "super-secret-value" not in repr(result)
    assert str(backend.received_secrets[0]) == "[REDACTED]"


def test_service_set_secret_raises_typed_error_without_echoing_secret_value() -> None:
    descriptor = CredentialDescriptor(
        provider_id="cerebras",
        label="Cerebras",
        expected_env_vars=("LOCAL_AI_AGENT_API_KEY", "CEREBRAS_API_KEY"),
        supports_fallback=False,
        write_env_var="LOCAL_AI_AGENT_API_KEY",
    )
    status = CredentialStatus(
        provider_id="cerebras",
        state=CredentialState.MISSING,
        source_kind=CredentialSourceKind.ENV,
        has_secret=False,
        missing_fields=("LOCAL_AI_AGENT_API_KEY", "CEREBRAS_API_KEY"),
        safe_summary="missing env secret",
    )
    backend = FakeBackend(descriptors=(descriptor,), statuses={"cerebras": status})
    service = HubCredentialService(backend)

    with pytest.raises(SecretValidationError) as exc_info:
        service.set_secret("cerebras", "   ", CredentialScope.PROCESS)

    assert "cannot be empty" in str(exc_info.value)
    assert "super-secret-value" not in str(exc_info.value)
