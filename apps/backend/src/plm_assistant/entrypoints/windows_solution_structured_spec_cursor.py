"""Fail-closed current-account key for StructuredSpec version-list signatures."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.solution.api.structured_spec_list_cursor import (
    StructuredSpecListCursorCodec,
)


STRUCTURED_SPEC_LIST_CURSOR_KEY_REF = "project-structured-spec-version-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionStructuredSpecCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("StructuredSpec list cursor key unavailable")


def create_windows_structured_spec_list_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> StructuredSpecListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            STRUCTURED_SPEC_LIST_CURSOR_KEY_REF)
        return StructuredSpecListCursorCodec(key)
    except Exception:
        raise ProductionStructuredSpecCursorStartupError() from None
