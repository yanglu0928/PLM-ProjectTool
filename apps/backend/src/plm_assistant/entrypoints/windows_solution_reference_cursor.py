"""Fail-closed current-account key for PROJECT Reference list signatures."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec
from plm_assistant.modules.solution.api.global_reference_list_cursor import GlobalReferenceListCursorCodec
from plm_assistant.modules.solution.application.global_reference_candidate_cursor import (
    GlobalReferenceCandidateCursorCodec,
)


REFERENCE_LIST_CURSOR_KEY_REF = "project-reference-list-cursor-v1"
GLOBAL_REFERENCE_LIST_CURSOR_KEY_REF = "global-reference-list-cursor-v1"
PROJECT_GLOBAL_REFERENCE_CANDIDATE_CURSOR_KEY_REF = (
    "project-global-reference-candidate-list-cursor-v1")


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


def create_windows_global_reference_list_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> GlobalReferenceListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            GLOBAL_REFERENCE_LIST_CURSOR_KEY_REF)
        return GlobalReferenceListCursorCodec(key)
    except Exception:
        raise ProductionReferenceCursorStartupError() from None


def create_windows_project_global_reference_candidate_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> GlobalReferenceCandidateCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            PROJECT_GLOBAL_REFERENCE_CANDIDATE_CURSOR_KEY_REF)
        return GlobalReferenceCandidateCursorCodec(key)
    except Exception:
        raise ProductionReferenceCursorStartupError() from None
