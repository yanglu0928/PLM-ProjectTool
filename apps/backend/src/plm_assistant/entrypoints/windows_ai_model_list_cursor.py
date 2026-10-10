"""Fail-closed Windows source for the dedicated AI Model list cursor key."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.ai.application.model_list_cursor import ModelListCursorCodec
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


AI_MODEL_LIST_CURSOR_KEY_REF = "ai-model-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionAIModelCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AI Model cursor key unavailable")


def create_windows_ai_model_list_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> ModelListCursorCodec:
    """Read only the current process account's dedicated, recoverable Vault key."""
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            AI_MODEL_LIST_CURSOR_KEY_REF,
        )
        return ModelListCursorCodec(key)
    except Exception:
        raise ProductionAIModelCursorStartupError() from None
