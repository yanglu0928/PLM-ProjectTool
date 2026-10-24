"""Opt-in Project Department history page with scoped opaque cursor."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.application.read_departments import (
    DepartmentPage, DepartmentView, ProjectDepartmentListQuery,
    ProjectDepartmentReadError, ProjectDepartmentReadService,
)


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)


def _public(view: DepartmentView) -> dict[str, object]:
    if (type(view) is not DepartmentView
            or type(view.department_id) is not uuid.UUID or view.department_id.int == 0
            or type(view.code) is not str or type(view.name) is not str
            or view.state not in {"ACTIVE", "INACTIVE"}
            or type(view.etag) is not str or _ETAG.fullmatch(view.etag) is None
            or not isinstance(view.created_at, datetime)
            or view.created_at.tzinfo is None or view.created_at.utcoffset() is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "department_id": str(view.department_id),
        "code": view.code,
        "name": view.name,
        "state": view.state,
        "created_at": view.created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "etag": view.etag,
    }


def _error(exc: ProjectDepartmentReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE"))


def create_project_department_read_router(*, sessions: SessionService,
                                          departments: ProjectDepartmentReadService,
                                          origins: LoginOriginPolicy,
                                          cursors: DepartmentListCursorCodec) -> APIRouter:
    if any(item is None for item in (sessions, departments, origins, cursors)):
        raise ValueError("session, department reads, origins and cursors are required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/departments")
    async def list_departments(project_id: uuid.UUID, request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token = _session_cookie(headers)
        try:
            await run_in_threadpool(sessions.validate, token)
        except SessionError:
            raise ApplicationError("AUTH_SESSION_EXPIRED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if project_id.int == 0:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        entries = list(request.query_params.multi_items())
        if (len(entries) > 2 or len({key for key, _ in entries}) != len(entries)
                or any(key not in {"page_size", "cursor"} for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        params = dict(entries)
        raw_size = params.get("page_size", "50")
        if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 200:
            raise ApplicationError("VALIDATION_FAILED")
        page_size = int(raw_size)
        after = (cursors.decode(params["cursor"], session_token=token,
                                project_id=project_id, page_size=page_size)
                 if "cursor" in params else None)
        try:
            page = await run_in_threadpool(
                departments.list_page,
                ProjectDepartmentListQuery(
                    token, uuid.UUID(request.state.trace_id), project_id,
                    after_department_id=after, limit=page_size,
                ),
            )
        except ProjectDepartmentReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not DepartmentPage or len(page.items) > page_size
                or any(type(item) is not DepartmentView for item in page.items)
                or page.has_more and (not page.items
                                      or page.next_after_department_id != page.items[-1].department_id)
                or not page.has_more and page.next_after_department_id is not None):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = (cursors.encode(
            session_token=token, project_id=project_id, page_size=page_size,
            department_id=page.next_after_department_id,
        ) if page.has_more else None)
        return JSONResponse({
            "data": {"items": [_public(item) for item in page.items],
                     "next_cursor": next_cursor, "has_more": page.has_more},
            "trace_id": request.state.trace_id,
        }, headers={"Cache-Control": "no-store"})

    return router
