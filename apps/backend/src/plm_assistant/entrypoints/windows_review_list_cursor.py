"""Fail-closed current-account key for encrypted Review-list cursors."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.review.api.list_cursor import ReviewListCursorCodec


REVIEW_LIST_CURSOR_KEY_REF = "review-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionReviewListCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Review list cursor key unavailable")


def create_windows_review_list_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> ReviewListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            REVIEW_LIST_CURSOR_KEY_REF,
        )
        return ReviewListCursorCodec(key)
    except Exception:
        raise ProductionReviewListCursorStartupError() from None
