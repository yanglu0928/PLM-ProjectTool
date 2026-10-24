"""Fail-closed Windows composition for the Secret-list cursor signing key."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


SECRET_LIST_CURSOR_KEY_REF = "secret-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionSecretCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("secret list cursor key unavailable")


def create_windows_secret_list_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> SecretListCursorCodec:
    """Use only the current process account's dedicated, recoverable Vault key."""
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            SECRET_LIST_CURSOR_KEY_REF,
        )
        return SecretListCursorCodec(key)
    except Exception:
        raise ProductionSecretCursorStartupError() from None
