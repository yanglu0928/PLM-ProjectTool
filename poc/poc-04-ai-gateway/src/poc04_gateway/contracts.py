from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays must not be negative")

    def delay_for_attempt(self, attempt: int) -> float:
        return min(self.base_delay_seconds * (2 ** max(attempt - 1, 0)), self.max_delay_seconds)


@dataclass(frozen=True, slots=True)
class AIRequest:
    task_type: str
    provider: str
    model: str
    messages: tuple[ChatMessage, ...]
    output_schema: dict[str, Any] | None = None
    max_tokens: int = 512
    temperature: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_type.strip():
            raise ValueError("task_type is required")
        if not self.provider.strip():
            raise ValueError("provider is required")
        if not self.model.strip():
            raise ValueError("model is required")
        if not self.messages:
            raise ValueError("at least one message is required")


@dataclass(frozen=True, slots=True)
class AIResponse:
    text: str
    model: str
    provider: str
    finish_reason: str | None
    usage: dict[str, Any]
    structured: dict[str, Any] | None = None
