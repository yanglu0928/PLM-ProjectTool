"""Fail-closed current-account key source for ParseRecord list cursors."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider


DOCUMENT_PARSE_CURSOR_KEY_REF = "document-parse-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionParseCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Document Parse cursor key unavailable")


def create_windows_document_parse_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> ParseListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            DOCUMENT_PARSE_CURSOR_KEY_REF,
        )
        return ParseListCursorCodec(key)
    except Exception:
        raise ProductionParseCursorStartupError() from None
