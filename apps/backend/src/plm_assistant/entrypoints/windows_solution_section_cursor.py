"""Fail-closed current-account key for SolutionSection list signatures."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.solution.api.section_list_cursor import SectionListCursorCodec


SECTION_LIST_CURSOR_KEY_REF = "project-section-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionSectionCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("SolutionSection list cursor key unavailable")


def create_windows_section_list_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> SectionListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            SECTION_LIST_CURSOR_KEY_REF)
        return SectionListCursorCodec(key)
    except Exception:
        raise ProductionSectionCursorStartupError() from None
