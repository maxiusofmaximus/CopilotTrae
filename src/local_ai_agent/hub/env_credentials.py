from __future__ import annotations

import os
from collections.abc import MutableMapping
from typing import Mapping, Sequence

from local_ai_agent.hub.credentials_contracts import (
    CredentialBackend,
    CredentialDescriptor,
    CredentialScope,
    CredentialSourceKind,
    CredentialState,
    CredentialStatus,
    CredentialWriteResult,
    SecretValue,
)


class CredentialBackendError(RuntimeError):
    """Base error for Hub credential backends."""


class CredentialWriteError(CredentialBackendError):
    """Raised when a backend cannot persist a secret."""


class CredentialDeleteError(CredentialBackendError):
    """Raised when a backend cannot delete a secret."""


class _EnvSecretSink:
    def __init__(self, env: MutableMapping[str, str], key: str) -> None:
        self._env = env
        self._key = key

    def accept_secret(self, secret: str) -> None:
        self._env[self._key] = secret


_DESCRIPTORS: tuple[CredentialDescriptor, ...] = (
    CredentialDescriptor(
        provider_id="cerebras",
        label="Cerebras",
        expected_env_vars=("LOCAL_AI_AGENT_API_KEY", "CEREBRAS_API_KEY"),
        supports_fallback=False,
        write_env_var="LOCAL_AI_AGENT_API_KEY",
    ),
    CredentialDescriptor(
        provider_id="openai_compatible",
        label="OpenAI Compatible",
        expected_env_vars=("LOCAL_AI_AGENT_API_KEY",),
        supports_fallback=False,
        write_env_var="LOCAL_AI_AGENT_API_KEY",
    ),
    CredentialDescriptor(
        provider_id="fallback",
        label="Fallback Provider",
        expected_env_vars=("LOCAL_AI_AGENT_FALLBACK_API_KEY",),
        supports_fallback=True,
        write_env_var="LOCAL_AI_AGENT_FALLBACK_API_KEY",
    ),
)


class EnvCredentialBackend(CredentialBackend):
    def __init__(self, process_env: MutableMapping[str, str] | None = None) -> None:
        self._process_env = process_env if process_env is not None else os.environ
        self._descriptors = {item.provider_id: item for item in _DESCRIPTORS}

    def list_descriptors(self) -> Sequence[CredentialDescriptor]:
        return tuple(self._descriptors.values())

    def get_status(self, provider_id: str) -> CredentialStatus:
        descriptor = self._get_descriptor(provider_id)
        present_keys = tuple(key for key in descriptor.expected_env_vars if self._process_env.get(key))
        if present_keys:
            return CredentialStatus(
                provider_id=provider_id,
                state=CredentialState.CONFIGURED,
                source_kind=CredentialSourceKind.ENV,
                has_secret=True,
                missing_fields=(),
                safe_summary="configured from env",
            )
        return CredentialStatus(
            provider_id=provider_id,
            state=CredentialState.MISSING,
            source_kind=CredentialSourceKind.ENV,
            has_secret=False,
            missing_fields=descriptor.expected_env_vars,
            safe_summary="missing env secret",
        )

    def set_secret(
        self,
        provider_id: str,
        secret: SecretValue,
        scope: CredentialScope,
    ) -> CredentialWriteResult:
        if scope is not CredentialScope.PROCESS:
            raise CredentialWriteError("Only process scope is supported by EnvCredentialBackend.")
        descriptor = self._get_descriptor(provider_id)
        if not descriptor.write_env_var:
            raise CredentialWriteError(f"Provider '{provider_id}' does not declare a writable env var.")
        sink = _EnvSecretSink(self._process_env, descriptor.write_env_var)
        secret.write_into(sink)
        return CredentialWriteResult(
            provider_id=provider_id,
            source_kind=CredentialSourceKind.ENV,
            scope=scope,
            changed_keys=(descriptor.write_env_var,),
        )

    def clear_secret(
        self,
        provider_id: str,
        scope: CredentialScope,
    ) -> CredentialWriteResult:
        if scope is not CredentialScope.PROCESS:
            raise CredentialDeleteError("Only process scope is supported by EnvCredentialBackend.")
        descriptor = self._get_descriptor(provider_id)
        changed_keys = tuple(key for key in descriptor.expected_env_vars if key in self._process_env)
        for key in changed_keys:
            del self._process_env[key]
        return CredentialWriteResult(
            provider_id=provider_id,
            source_kind=CredentialSourceKind.ENV,
            scope=scope,
            changed_keys=changed_keys,
        )

    def build_launch_env(
        self,
        base_env: Mapping[str, str],
        provider_id: str,
    ) -> dict[str, str]:
        descriptor = self._get_descriptor(provider_id)
        launch_env = dict(base_env)
        for key in descriptor.expected_env_vars:
            value = self._process_env.get(key)
            if value:
                launch_env[key] = value
        return launch_env

    def _get_descriptor(self, provider_id: str) -> CredentialDescriptor:
        try:
            return self._descriptors[provider_id]
        except KeyError as exc:
            raise CredentialBackendError(f"Unknown provider: {provider_id}") from exc
