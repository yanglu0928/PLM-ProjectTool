"""Fail-closed current-account Vault key for OutputRequest list cursors."""
from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.output.api.list_cursor import OutputRequestListCursorCodec
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


OUTPUT_REQUEST_LIST_CURSOR_KEY_REF = "output-request-list-cursor-v1"


class OutputRequestListCursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionOutputRequestListCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("OutputRequest list cursor key unavailable")


def create_windows_output_request_list_cursor_codec(
    *, resolver: OutputRequestListCursorKeyResolverPort | None = None,
) -> OutputRequestListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            OUTPUT_REQUEST_LIST_CURSOR_KEY_REF)
        return OutputRequestListCursorCodec(key)
    except Exception:
        raise ProductionOutputRequestListCursorStartupError() from None
