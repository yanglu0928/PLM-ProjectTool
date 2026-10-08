"""Fail-closed current-account key for PROJECT Reference list signatures."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec


REFERENCE_LIST_CURSOR_KEY_REF = "project-reference-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionReferenceCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Reference list cursor key unavailable")


def create_windows_project_reference_list_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> ReferenceListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            REFERENCE_LIST_CURSOR_KEY_REF)
        return ReferenceListCursorCodec(key)
    except Exception:
        raise ProductionReferenceCursorStartupError() from None
