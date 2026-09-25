"""Fail-closed Windows source for ProjectMember-list cursor signatures."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec


PROJECT_MEMBER_CURSOR_KEY_REF = "project-member-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionMemberCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("project member cursor key unavailable")


def create_windows_project_member_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> MemberListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            PROJECT_MEMBER_CURSOR_KEY_REF,
        )
        return MemberListCursorCodec(key)
    except Exception:
        raise ProductionMemberCursorStartupError() from None
