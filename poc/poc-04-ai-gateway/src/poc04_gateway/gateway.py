from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import replace

from jsonschema import Draft202012Validator

from .contracts import AIRequest, AIResponse, RetryPolicy
from .errors import AIError
from .provider import ProviderAdapter


class ModelRouter:
    def __init__(self) -> None:
        self._providers: dict[str, ProviderAdapter] = {}

    def register(self, adapter: ProviderAdapter) -> None:
        if adapter.provider_id in self._providers:
            raise ValueError(f"provider already registered: {adapter.provider_id}")
        self._providers[adapter.provider_id] = adapter

    def resolve(self, provider_id: str) -> ProviderAdapter:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise AIError("AI_PROVIDER_NOT_CONFIGURED", "AI provider is not configured.") from exc

    def close(self) -> None:
        for adapter in self._providers.values():
            adapter.close()


class AIService:
    def __init__(
        self,
        router: ModelRouter,
        *,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._router = router
        self._retry_policy = retry_policy or RetryPolicy()
        self._sleep = sleep

    def _retry_or_raise(self, exc: AIError, attempt: int) -> None:
        if not exc.retryable or attempt >= self._retry_policy.max_attempts:
            raise exc
        self._sleep(self._retry_policy.delay_for_attempt(attempt))

    @staticmethod
    def _validate_structured(request: AIRequest, response: AIResponse) -> AIResponse:
        if request.output_schema is None:
            return response
        try:
            structured = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise AIError(
                "AI_JSON_INVALID",
                "AI provider did not return valid JSON.",
                retryable=True,
            ) from exc
        errors = sorted(
            Draft202012Validator(request.output_schema).iter_errors(structured), key=str
        )
        if errors or not isinstance(structured, dict):
            raise AIError(
                "AI_SCHEMA_INVALID",
                "AI provider output failed schema validation.",
                retryable=True,
            )
        return replace(response, structured=structured)

    def complete(self, request: AIRequest) -> AIResponse:
        provider = self._router.resolve(request.provider)
        for attempt in range(1, self._retry_policy.max_attempts + 1):
            try:
                response = provider.complete(request)
                return self._validate_structured(request, response)
            except AIError as exc:
                self._retry_or_raise(exc, attempt)
        raise AIError("AI_INTERNAL", "AI response was not produced.")  # pragma: no cover

    def stream(self, request: AIRequest) -> Iterator[str]:
        provider = self._router.resolve(request.provider)
        for attempt in range(1, self._retry_policy.max_attempts + 1):
            emitted = False
            try:
                for chunk in provider.stream(request):
                    emitted = True
                    yield chunk
                return
            except AIError as exc:
                if emitted:
                    raise AIError(
                        "AI_STREAM_INTERRUPTED",
                        "AI stream failed after output started; automatic retry is unsafe.",
                    ) from exc
                self._retry_or_raise(exc, attempt)
