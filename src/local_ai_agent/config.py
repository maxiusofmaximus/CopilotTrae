from __future__ import annotations

import os
from datetime import datetime, UTC
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_SYSTEM_PROMPT = (
    "You are a production-grade workflow assistant. "
    "Respond clearly, structure the answer for real operational use, "
    "and call out risks or next actions when helpful."
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _default_session_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _read_dotenv(dotenv_path: Path) -> dict[str, str]:
    if not dotenv_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


class Settings(BaseModel):
    provider: str = "cerebras"
    fallback_provider: str | None = None
    api_key: str | None = None
    fallback_api_key: str | None = None
    base_url: str = "https://api.cerebras.ai/v1"
    fallback_base_url: str | None = None
    model: str = "gpt-oss-120b"
    fallback_model: str | None = None
    stub_response_text: str = "Stub response"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    temperature: float = 0.2
    max_tokens: int = 1024
    timeout_seconds: float = 30.0
    max_retries: int = 3
    max_memory_messages: int = 8
    persistent_memory_enabled: bool = False
    memory_dir: Path = Field(default_factory=lambda: Path("memory"))
    confirm_before_copy: bool = True
    logs_dir: Path = Field(default_factory=lambda: Path("logs"))
    session_id: str = Field(default_factory=_default_session_id)
    tesseract_command: str = "bin/tesseract/tesseract.exe"

    @classmethod
    def from_env(cls) -> "Settings":
        dotenv_values = _read_dotenv(PROJECT_ROOT / ".env")
        env = {**dotenv_values, **os.environ}
        return cls(
            provider=env.get("LOCAL_AI_AGENT_PROVIDER", "cerebras"),
            fallback_provider=env.get("LOCAL_AI_AGENT_FALLBACK_PROVIDER") or None,
            api_key=env.get("LOCAL_AI_AGENT_API_KEY") or env.get("CEREBRAS_API_KEY"),
            fallback_api_key=env.get("LOCAL_AI_AGENT_FALLBACK_API_KEY") or None,
            base_url=env.get("LOCAL_AI_AGENT_BASE_URL", "https://api.cerebras.ai/v1"),
            fallback_base_url=env.get("LOCAL_AI_AGENT_FALLBACK_BASE_URL") or None,
            model=env.get("LOCAL_AI_AGENT_MODEL", "gpt-oss-120b"),
            fallback_model=env.get("LOCAL_AI_AGENT_FALLBACK_MODEL") or None,
            stub_response_text=env.get("LOCAL_AI_AGENT_STUB_RESPONSE_TEXT", "Stub response"),
            system_prompt=env.get("LOCAL_AI_AGENT_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
            temperature=float(env.get("LOCAL_AI_AGENT_TEMPERATURE", "0.2")),
            max_tokens=int(env.get("LOCAL_AI_AGENT_MAX_TOKENS", "1024")),
            timeout_seconds=float(env.get("LOCAL_AI_AGENT_TIMEOUT_SECONDS", "30")),
            max_retries=int(env.get("LOCAL_AI_AGENT_MAX_RETRIES", "3")),
            max_memory_messages=int(env.get("LOCAL_AI_AGENT_MAX_MEMORY_MESSAGES", "8")),
            persistent_memory_enabled=env.get("LOCAL_AI_AGENT_PERSISTENT_MEMORY", "false").lower()
            in {"1", "true", "yes", "on"},
            memory_dir=Path(env.get("LOCAL_AI_AGENT_MEMORY_DIR", "memory")),
            confirm_before_copy=env.get("LOCAL_AI_AGENT_CONFIRM_BEFORE_COPY", "true").lower()
            in {"1", "true", "yes", "on"},
            logs_dir=Path(env.get("LOCAL_AI_AGENT_LOGS_DIR", "logs")),
            session_id=env.get("LOCAL_AI_AGENT_SESSION_ID", _default_session_id()),
            tesseract_command=env.get("LOCAL_AI_AGENT_TESSERACT_COMMAND", "bin/tesseract/tesseract.exe"),
        )
