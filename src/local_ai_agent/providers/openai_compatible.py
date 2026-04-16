from __future__ import annotations

import time
from typing import Any

import httpx

from local_ai_agent.models import ChatRequest, ChatResponse, TokenUsage
from local_ai_agent.providers.base import (
    ProviderConfigError,
    ProviderResponseError,
    ProviderTransportError,
)


class GenericOpenAICompatibleClient:
    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        timeout_seconds: float,
        max_retries: int,
        model: str,
        provider_name: str = "openai_compatible",
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ProviderConfigError("Missing API key for openai_compatible provider.")

        self.provider_name = provider_name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._api_key = api_key
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            headers=self._request_headers(),
        )

    def complete(self, request: ChatRequest) -> ChatResponse:
        last_error: Exception | None = None
        payload = request.to_payload()
        payload["model"] = self.model

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._client.post(
                    "/chat/completions",
                    json=payload,
                    headers=self._request_headers(),
                )
                if response.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(min(0.25 * attempt, 1.0))
                    continue
                response.raise_for_status()
                return self._parse_response(response.json())
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(min(0.25 * attempt, 1.0))
                    continue
                raise ProviderTransportError(f"{self.provider_name} request failed: {exc}") from exc
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(min(0.25 * attempt, 1.0))
                    continue
                raise ProviderTransportError(f"{self.provider_name} transport error: {exc}") from exc

        raise ProviderTransportError(f"{self.provider_name} request failed after retries: {last_error}")

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _request_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _parse_response(self, payload: dict[str, Any]) -> ChatResponse:
        try:
            choice = payload["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError("Invalid openai_compatible response payload.") from exc

        usage_payload = payload.get("usage") or {}
        usage = TokenUsage.model_validate(usage_payload) if usage_payload else None

        return ChatResponse(
            provider=self.provider_name,
            model=payload.get("model", self.model),
            content=content,
            finish_reason=choice.get("finish_reason"),
            usage=usage,
        )
