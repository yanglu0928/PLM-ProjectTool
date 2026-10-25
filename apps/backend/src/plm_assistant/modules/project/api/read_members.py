"""Opt-in ProjectMember history page with scoped opaque cursor."""

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
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.project.application.read_members import (
    ProjectMemberListQuery, ProjectMemberPage, ProjectMemberReadError,
    ProjectMemberReadService, ProjectMemberView,
)


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)


def _date(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _public(view: ProjectMemberView) -> dict[str, object]:
    if (type(view) is not ProjectMemberView
            or type(view.member_id) is not uuid.UUID or view.member_id.int == 0
            or type(view.user_id) is not uuid.UUID or view.user_id.int == 0
            or type(view.department_id) is not uuid.UUID or view.department_id.int == 0
            or type(view.user_display_name) is not str
            or type(view.department_name) is not str
            or type(view.etag) is not str or _ETAG.fullmatch(view.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "member_id": str(view.member_id),
        "user": {"user_id": str(view.user_id), "display_name": view.user_display_name},
        "role": view.role,
        "department": {"department_id": str(view.department_id),
                       "name": view.department_name},
        "state": view.state,
        "effective_at": _date(view.effective_at),
        "ended_at": _date(view.ended_at) if view.ended_at is not None else None,
        "etag": view.etag,
    }


def _error(exc: ProjectMemberReadError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def create_project_member_read_router(*, sessions: SessionService,
                                      members: ProjectMemberReadService,
                                      origins: LoginOriginPolicy,
                                      cursors: MemberListCursorCodec) -> APIRouter:
    if any(item is None for item in (sessions, members, origins, cursors)):
        raise ValueError("session, member reads, origins and cursors are required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/members")
    async def list_members(project_id: uuid.UUID, request: Request) -> JSONResponse:
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
                members.list_page,
                ProjectMemberListQuery(token, uuid.UUID(request.state.trace_id),
                                       project_id, after_member_id=after, limit=page_size),
            )
        except ProjectMemberReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not ProjectMemberPage or len(page.items) > page_size
                or any(type(item) is not ProjectMemberView for item in page.items)
                or page.has_more and (not page.items
                                      or page.next_after_member_id != page.items[-1].member_id)
                or not page.has_more and page.next_after_member_id is not None):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = (cursors.encode(
            session_token=token, project_id=project_id, page_size=page_size,
            member_id=page.next_after_member_id,
        ) if page.has_more else None)
        return JSONResponse({
            "data": {"items": [_public(item) for item in page.items],
                     "next_cursor": next_cursor, "has_more": page.has_more},
            "trace_id": request.state.trace_id,
        }, headers={"Cache-Control": "no-store"})

    return router
