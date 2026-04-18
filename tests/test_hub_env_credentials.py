from __future__ import annotations

import pytest

from local_ai_agent.hub.credentials_contracts import (
    CredentialScope,
    CredentialSourceKind,
    CredentialState,
    SecretValue,
)
from local_ai_agent.hub.env_credentials import (
    CredentialWriteError,
    EnvCredentialBackend,
)


def test_env_backend_lists_known_provider_descriptors() -> None:
    backend = EnvCredentialBackend(process_env={})

    descriptors = {item.provider_id: item for item in backend.list_descriptors()}

    assert set(descriptors) == {"cerebras", "openai_compatible", "fallback"}
    assert descriptors["cerebras"].expected_env_vars == (
        "LOCAL_AI_AGENT_API_KEY",
        "CEREBRAS_API_KEY",
    )
    assert descriptors["fallback"].expected_env_vars == ("LOCAL_AI_AGENT_FALLBACK_API_KEY",)


def test_env_backend_reports_cerebras_configured_when_local_api_key_present() -> None:
    backend = EnvCredentialBackend(process_env={"LOCAL_AI_AGENT_API_KEY": "test-key"})

    status = backend.get_status("cerebras")

    assert status.state is CredentialState.CONFIGURED
    assert status.has_secret is True
    assert status.source_kind is CredentialSourceKind.ENV


def test_env_backend_reports_cerebras_configured_when_cerebras_api_key_present() -> None:
    backend = EnvCredentialBackend(process_env={"CEREBRAS_API_KEY": "test-key"})

    status = backend.get_status("cerebras")

    assert status.state is CredentialState.CONFIGURED
    assert status.has_secret is True
    assert status.source_kind is CredentialSourceKind.ENV


def test_env_backend_set_secret_derives_write_key_from_provider_descriptor() -> None:
    process_env: dict[str, str] = {}
    backend = EnvCredentialBackend(process_env=process_env)

    primary_result = backend.set_secret(
        "cerebras",
        SecretValue("primary-key"),
        CredentialScope.PROCESS,
    )
    fallback_result = backend.set_secret(
        "fallback",
        SecretValue("fallback-key"),
        CredentialScope.PROCESS,
    )

    assert primary_result.changed_keys == ("LOCAL_AI_AGENT_API_KEY",)
    assert fallback_result.changed_keys == ("LOCAL_AI_AGENT_FALLBACK_API_KEY",)
    assert process_env["LOCAL_AI_AGENT_API_KEY"] == "primary-key"
    assert process_env["LOCAL_AI_AGENT_FALLBACK_API_KEY"] == "fallback-key"
    assert "CEREBRAS_API_KEY" not in process_env


def test_env_backend_set_secret_raises_typed_error_for_user_scope() -> None:
    backend = EnvCredentialBackend(process_env={})

    with pytest.raises(CredentialWriteError, match="Only process scope is supported"):
        backend.set_secret("cerebras", SecretValue("primary-key"), CredentialScope.USER)


def test_env_backend_clear_secret_removes_only_provider_owned_keys() -> None:
    process_env = {
        "LOCAL_AI_AGENT_API_KEY": "primary-key",
        "CEREBRAS_API_KEY": "secondary-key",
        "LOCAL_AI_AGENT_FALLBACK_API_KEY": "fallback-key",
        "LOCAL_AI_AGENT_PROVIDER": "cerebras",
    }
    backend = EnvCredentialBackend(process_env=process_env)

    result = backend.clear_secret("cerebras", CredentialScope.PROCESS)

    assert result.changed_keys == ("LOCAL_AI_AGENT_API_KEY", "CEREBRAS_API_KEY")
    assert "LOCAL_AI_AGENT_API_KEY" not in process_env
    assert "CEREBRAS_API_KEY" not in process_env
    assert process_env["LOCAL_AI_AGENT_FALLBACK_API_KEY"] == "fallback-key"
    assert process_env["LOCAL_AI_AGENT_PROVIDER"] == "cerebras"


def test_env_backend_build_launch_env_returns_copy_without_mutating_input() -> None:
    backend = EnvCredentialBackend(
        process_env={
            "LOCAL_AI_AGENT_API_KEY": "primary-key",
            "LOCAL_AI_AGENT_BASE_URL": "https://api.cerebras.ai/v1",
        }
    )
    base_env = {"LOCAL_AI_AGENT_PROVIDER": "cerebras"}

    launch_env = backend.build_launch_env(base_env, "cerebras")

    assert launch_env is not base_env
    assert launch_env["LOCAL_AI_AGENT_PROVIDER"] == "cerebras"
    assert launch_env["LOCAL_AI_AGENT_API_KEY"] == "primary-key"
    assert base_env == {"LOCAL_AI_AGENT_PROVIDER": "cerebras"}
