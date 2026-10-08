"""Fail-closed current-account key for SolutionOutline list signatures."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.solution.api.outline_list_cursor import OutlineListCursorCodec


OUTLINE_LIST_CURSOR_KEY_REF = "project-outline-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionOutlineCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("SolutionOutline list cursor key unavailable")


def create_windows_outline_list_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> OutlineListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            OUTLINE_LIST_CURSOR_KEY_REF)
        return OutlineListCursorCodec(key)
    except Exception:
        raise ProductionOutlineCursorStartupError() from None
