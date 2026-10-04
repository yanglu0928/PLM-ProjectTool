"""Opt-in one-way Project archive HTTP boundary."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.project.api.patch_project import _error
from plm_assistant.modules.project.api.read_projects import project_view_data
from plm_assistant.modules.project.application.read_projects import ProjectView
from plm_assistant.modules.project.application.write_project import (
    ArchiveProject, ProjectWriteError, ProjectWriteService,
)


def create_project_archive_router(*, sessions: SessionService,
                                  writes: ProjectWriteService,
                                  origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or writes is None or origins is None:
        raise ValueError("session, Project writes and origins are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}:archive")
    async def archive_project(project_id: uuid.UUID, request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token = _session_cookie(headers)
        csrf = _csrf_header(headers)
        key = _idempotency_header(headers)
        try:
            await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True,
            )
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        expected = parse_if_match(headers)
        if project_id.int == 0:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        async for chunk in request.stream():
            if chunk:
                raise ApplicationError("REQUEST_MALFORMED")
        try:
            view = await run_in_threadpool(
                writes.archive_idempotent,
                ArchiveProject(token, csrf, uuid.UUID(request.state.trace_id),
                               project_id, expected),
                idempotency_key=key,
            )
        except ProjectWriteError as exc:
            if exc.code == "CONFLICT_IDEMPOTENCY":
                raise ApplicationError("CONFLICT_IDEMPOTENCY") from None
            raise _error(exc) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not ProjectView or view.state != "ARCHIVED":
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": project_view_data(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    return router
