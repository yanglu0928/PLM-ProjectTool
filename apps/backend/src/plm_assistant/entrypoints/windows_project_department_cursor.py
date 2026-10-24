"""Fail-closed Windows source for ProjectDepartment-list cursor signatures."""

from __future__ import annotations

from typing import Protocol

from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec


PROJECT_DEPARTMENT_CURSOR_KEY_REF = "project-department-list-cursor-v1"


class CursorKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionDepartmentCursorStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("project department cursor key unavailable")


def create_windows_project_department_cursor_codec(
    *, resolver: CursorKeyResolverPort | None = None,
) -> DepartmentListCursorCodec:
    try:
        key = (resolver or WindowsSecretKeyProvider()).resolve_key(
            PROJECT_DEPARTMENT_CURSOR_KEY_REF,
        )
        return DepartmentListCursorCodec(key)
    except Exception:
        raise ProductionDepartmentCursorStartupError() from None
