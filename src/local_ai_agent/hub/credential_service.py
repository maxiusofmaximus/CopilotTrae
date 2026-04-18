from __future__ import annotations

from typing import Mapping

from local_ai_agent.hub.credentials_contracts import (
    CredentialBackend,
    CredentialDescriptor,
    CredentialScope,
    CredentialState,
    CredentialStatus,
    CredentialWriteResult,
    SecretValue,
)


class HubCredentialServiceError(RuntimeError):
    """Base error for Hub credential service operations."""


class UnknownProviderError(HubCredentialServiceError):
    """Raised when a provider is not known by the service."""


class SecretValidationError(HubCredentialServiceError):
    """Raised when secret input fails structural validation."""


class LaunchEnvBuildError(HubCredentialServiceError):
    """Raised when launch environment assembly fails."""


class HubCredentialService:
    def __init__(self, backend: CredentialBackend) -> None:
        self._backend = backend
        self._descriptors = {item.provider_id: item for item in backend.list_descriptors()}

    def list_credentials(self) -> tuple[CredentialDescriptor, ...]:
        return tuple(self._descriptors.values())

    def validate_provider_setup(self, provider_id: str) -> CredentialStatus:
        descriptor = self._get_descriptor(provider_id)
        status = self._backend.get_status(provider_id)
        if status.has_secret:
            return CredentialStatus(
                provider_id=provider_id,
                state=CredentialState.CONFIGURED,
                source_kind=status.source_kind,
                has_secret=True,
                missing_fields=(),
                safe_summary=status.safe_summary,
            )
        return CredentialStatus(
            provider_id=provider_id,
            state=CredentialState.MISSING,
            source_kind=status.source_kind,
            has_secret=False,
            missing_fields=descriptor.expected_env_vars,
            safe_summary=status.safe_summary,
        )

    def set_secret(
        self,
        provider_id: str,
        secret: str,
        scope: CredentialScope,
    ) -> CredentialWriteResult:
        self._get_descriptor(provider_id)
        try:
            validated_secret = SecretValue(secret)
        except ValueError as exc:
            raise SecretValidationError("Secret value cannot be empty.") from exc
        return self._backend.set_secret(provider_id, validated_secret, scope)

    def clear_secret(
        self,
        provider_id: str,
        scope: CredentialScope,
    ) -> CredentialWriteResult:
        self._get_descriptor(provider_id)
        return self._backend.clear_secret(provider_id, scope)

    def build_launch_env(
        self,
        base_env: Mapping[str, str],
        provider_id: str,
    ) -> dict[str, str]:
        self._get_descriptor(provider_id)
        try:
            return self._backend.build_launch_env(base_env, provider_id)
        except Exception as exc:
            raise LaunchEnvBuildError(f"Failed to build launch env for provider '{provider_id}'.") from exc

    def _get_descriptor(self, provider_id: str) -> CredentialDescriptor:
        try:
            return self._descriptors[provider_id]
        except KeyError as exc:
            raise UnknownProviderError(f"Unknown provider: {provider_id}") from exc
