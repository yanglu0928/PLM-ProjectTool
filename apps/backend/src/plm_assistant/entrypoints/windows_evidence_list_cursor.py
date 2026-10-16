"""Fail-closed current-account key source for Evidence list cursors."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.evidence.api.list_cursor import EvidenceListCursorCodec
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import WindowsSecretKeyProvider


EVIDENCE_LIST_CURSOR_KEY_REF = "evidence-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionEvidenceCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Evidence cursor key unavailable")


def create_windows_evidence_list_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> EvidenceListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            EVIDENCE_LIST_CURSOR_KEY_REF,
        )
        return EvidenceListCursorCodec(key)
    except Exception:
        raise ProductionEvidenceCursorStartupError() from None
