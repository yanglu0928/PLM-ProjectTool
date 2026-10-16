"""Fail-closed current-account key for OutlineVersion history pagination."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.solution.api.outline_version_list_cursor import (
    OutlineVersionListCursorCodec,
)


OUTLINE_VERSION_LIST_CURSOR_KEY_REF = "project-outline-version-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionOutlineVersionCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("OutlineVersion history cursor key unavailable")


def create_windows_outline_version_list_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> OutlineVersionListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            OUTLINE_VERSION_LIST_CURSOR_KEY_REF)
        return OutlineVersionListCursorCodec(key)
    except Exception:
        raise ProductionOutlineVersionCursorStartupError() from None
