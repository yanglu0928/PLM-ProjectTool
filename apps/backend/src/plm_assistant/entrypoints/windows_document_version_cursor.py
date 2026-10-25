"""Fail-closed current-account key source for DocumentVersion list cursors."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider


DOCUMENT_VERSION_CURSOR_KEY_REF = "document-version-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionVersionCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("DocumentVersion cursor key unavailable")


def create_windows_document_version_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> VersionListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            DOCUMENT_VERSION_CURSOR_KEY_REF,
        )
        return VersionListCursorCodec(key)
    except Exception:
        raise ProductionVersionCursorStartupError() from None
