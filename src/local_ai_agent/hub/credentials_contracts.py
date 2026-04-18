from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol, Sequence


class CredentialState(str, Enum):
    CONFIGURED = "configured"
    MISSING = "missing"
    PARTIAL = "partial"
    INVALID = "invalid"


class CredentialSourceKind(str, Enum):
    ENV = "env"
    SECURE_STORE = "secure_store"
    NONE = "none"


class CredentialScope(str, Enum):
    PROCESS = "process"
    USER = "user"


@dataclass(frozen=True)
class CredentialDescriptor:
    provider_id: str
    label: str
    expected_env_vars: tuple[str, ...]
    supports_fallback: bool


@dataclass(frozen=True)
class CredentialStatus:
    provider_id: str
    state: CredentialState
    source_kind: CredentialSourceKind
    has_secret: bool
    missing_fields: tuple[str, ...]
    safe_summary: str


@dataclass(frozen=True)
class CredentialWriteResult:
    provider_id: str
    source_kind: CredentialSourceKind
    scope: CredentialScope | str
    changed_keys: tuple[str, ...]


class SecretSink(Protocol):
    def accept_secret(self, secret: str) -> None: ...


class SecretValue:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not value or not value.strip():
            raise ValueError("SecretValue cannot be empty.")
        self._value = value

    def __repr__(self) -> str:
        return "[REDACTED]"

    def __str__(self) -> str:
        return "[REDACTED]"

    def write_into(self, sink: SecretSink) -> None:
        sink.accept_secret(self._value)


class CredentialBackend(Protocol):
    def list_descriptors(self) -> Sequence[CredentialDescriptor]: ...

    def get_status(self, provider_id: str) -> CredentialStatus: ...

    def set_secret(
        self,
        provider_id: str,
        secret: SecretValue,
        scope: CredentialScope,
    ) -> CredentialWriteResult: ...

    def clear_secret(
        self,
        provider_id: str,
        scope: CredentialScope,
    ) -> CredentialWriteResult: ...

    def build_launch_env(
        self,
        base_env: Mapping[str, str],
        provider_id: str,
    ) -> dict[str, str]: ...

