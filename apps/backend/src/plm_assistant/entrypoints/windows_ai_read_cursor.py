"""Fail-closed current-account source for AI read pagination cursors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.ai.api.invocation_list_cursor import (
    AIInvocationListCursorCodec,
)
from plm_assistant.modules.ai.api.task_list_cursor import AITaskListCursorCodec
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


AI_READ_CURSOR_KEY_REF = "ai-read-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionAIReadCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AI read cursor key unavailable")


@dataclass(frozen=True, slots=True)
class WindowsAIReadCursorCodecs:
    task: AITaskListCursorCodec
    invocation: AIInvocationListCursorCodec

    def __post_init__(self) -> None:
        if (type(self.task) is not AITaskListCursorCodec
                or type(self.invocation) is not AIInvocationListCursorCodec):
            raise ProductionAIReadCursorStartupError()


def create_windows_ai_read_cursor_codecs(
    *, resolver: CursorKeyResolverPort | None = None,
) -> WindowsAIReadCursorCodecs:
    """Read one recoverable key, then domain-separate Task and Invocation AEAD."""
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            AI_READ_CURSOR_KEY_REF,
        )
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("invalid AI read cursor key")
        return WindowsAIReadCursorCodecs(
            AITaskListCursorCodec(key), AIInvocationListCursorCodec(key),
        )
    except Exception:
        raise ProductionAIReadCursorStartupError() from None
