"""Fail-closed Windows source for the dedicated AI Prompt list cursor key."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.ai.application.prompt_list_cursor import PromptListCursorCodec
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


AI_PROMPT_LIST_CURSOR_KEY_REF = "ai-prompt-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionAIPromptCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AI Prompt cursor key unavailable")


def create_windows_ai_prompt_list_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> PromptListCursorCodec:
    """Read only the current process account's dedicated, recoverable Vault key."""
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            AI_PROMPT_LIST_CURSOR_KEY_REF,
        )
        return PromptListCursorCodec(key)
    except Exception:
        raise ProductionAIPromptCursorStartupError() from None
