"""Fail-closed current-account key source for Document list cursors."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider


DOCUMENT_LIST_CURSOR_KEY_REF = "document-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionDocumentCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Document cursor key unavailable")


def create_windows_document_list_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> DocumentListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            DOCUMENT_LIST_CURSOR_KEY_REF,
        )
        return DocumentListCursorCodec(key)
    except Exception:
        raise ProductionDocumentCursorStartupError() from None
