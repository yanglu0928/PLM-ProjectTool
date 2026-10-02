"""Fail-closed Windows source for the dedicated AI Provider list cursor key."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.ai.application.provider_list_cursor import ProviderListCursorCodec
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


AI_PROVIDER_LIST_CURSOR_KEY_REF = "ai-provider-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionAIProviderCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AI Provider cursor key unavailable")


def create_windows_ai_provider_list_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> ProviderListCursorCodec:
    """Read only the current process account's dedicated, recoverable Vault key."""
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            AI_PROVIDER_LIST_CURSOR_KEY_REF,
        )
        return ProviderListCursorCodec(key)
    except Exception:
        raise ProductionAIProviderCursorStartupError() from None
