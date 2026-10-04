from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, Protocol

import httpx

from .contracts import AIRequest, AIResponse
from .errors import AIError, error_for_status


class ProviderAdapter(Protocol):
    provider_id: str

    def complete(self, request: AIRequest) -> AIResponse: ...

    def stream(self, request: AIRequest) -> Iterator[str]: ...

    def close(self) -> None: ...


class DeepSeekAdapter:
    provider_id = "deepseek"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key is required")
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )

    @staticmethod
    def _payload(request: AIRequest, *, stream: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": stream,
        }
        if request.output_schema is not None:
            payload["response_format"] = {"type": "json_object"}
        if request.thinking is not None:
            payload["thinking"] = {"type": request.thinking}
        return payload

    @staticmethod
    def _request_error(exc: httpx.HTTPError) -> AIError:
        if isinstance(exc, httpx.TimeoutException):
            return AIError("AI_TIMEOUT", "AI provider request timed out.", retryable=True)
        return AIError("AI_NETWORK_ERROR", "AI provider network request failed.", retryable=True)

    def complete(self, request: AIRequest) -> AIResponse:
        try:
            response = self._client.post(
                "/chat/completions", json=self._payload(request, stream=False)
            )
        except httpx.HTTPError as exc:
            raise self._request_error(exc) from exc
        if response.status_code >= 400:
            raise error_for_status(response.status_code)
        try:
            body = response.json()
            choice = body["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AIError("AI_RESPONSE_INVALID", "AI provider response is invalid.") from exc
        if not isinstance(text, str):
            raise AIError("AI_RESPONSE_INVALID", "AI provider response content is not text.")
        return AIResponse(
            text=text,
            model=str(body.get("model", request.model)),
            provider=self.provider_id,
            finish_reason=choice.get("finish_reason"),
            usage=body.get("usage") or {},
        )

    def stream(self, request: AIRequest) -> Iterator[str]:
        try:
            with self._client.stream(
                "POST", "/chat/completions", json=self._payload(request, stream=True)
            ) as response:
                if response.status_code >= 400:
                    raise error_for_status(response.status_code)
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        return
                    try:
                        event = json.loads(data)
                        delta = event["choices"][0]["delta"].get("content")
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
                        raise AIError("AI_STREAM_INVALID", "AI provider stream event is invalid.") from exc
                    if delta:
                        yield str(delta)
        except AIError:
            raise
        except httpx.HTTPError as exc:
            raise self._request_error(exc) from exc

    def close(self) -> None:
        self._client.close()
