"""Fail-closed current-account key for SectionVersion history pagination."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.solution.api.section_version_list_cursor import (
    SectionVersionListCursorCodec,
)


SECTION_VERSION_LIST_CURSOR_KEY_REF = "project-section-version-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionSectionVersionCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("SectionVersion history cursor key unavailable")


def create_windows_section_version_list_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> SectionVersionListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            SECTION_VERSION_LIST_CURSOR_KEY_REF)
        return SectionVersionListCursorCodec(key)
    except Exception:
        raise ProductionSectionVersionCursorStartupError() from None
