"""Opt-in Project list and detail HTTP projection."""

from __future__ import annotations

import re
import uuid
from datetime import timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.project.application.read_projects import (
    ProjectReadError, ProjectReadQuery, ProjectReadService, ProjectView,
)


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)


def _public(view: ProjectView) -> dict[str, object]:
    if (type(view) is not ProjectView or view.created_at.tzinfo is None
            or view.created_at.utcoffset() is None
            or not re.fullmatch(r'"v(0|[1-9][0-9]*)"', view.etag)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "project_id": str(view.project_id), "code": view.code,
        "name": view.name, "state": view.state,
        "created_at": view.created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "etag": view.etag,
    }


def _error(exc: ProjectReadError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


async def _query(request: Request, *, sessions: SessionService,
                 origins: LoginOriginPolicy) -> ProjectReadQuery:
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
    return ProjectReadQuery(token, uuid.UUID(request.state.trace_id))


def create_project_read_router(*, sessions: SessionService,
                               projects: ProjectReadService,
                               origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or projects is None or origins is None:
        raise ValueError("session, Project reads and origins are required")
    router = APIRouter()

    @router.get("/api/v1/projects")
    async def list_projects(request: Request) -> JSONResponse:
        query = await _query(request, sessions=sessions, origins=origins)
        entries = list(request.query_params.multi_items())
        if (len(entries) > 1 or any(key != "page_size" for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        raw_size = entries[0][1] if entries else "50"
        if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 200:
            raise ApplicationError("VALIDATION_FAILED")
        try:
            page = await run_in_threadpool(projects.list, query)
        except ProjectReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if page.next_cursor is not None or page.has_more or len(page.items) > int(raw_size):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({
            "data": {"items": [_public(item) for item in page.items],
                     "next_cursor": None, "has_more": False},
            "trace_id": request.state.trace_id,
        }, headers={"Cache-Control": "no-store"})

    @router.get("/api/v1/projects/{project_id}")
    async def get_project(project_id: uuid.UUID, request: Request) -> JSONResponse:
        query = await _query(request, sessions=sessions, origins=origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            view = await run_in_threadpool(projects.get, query, project_id)
        except ProjectReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        body = _public(view)
        return JSONResponse(
            {"data": body, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    return router
