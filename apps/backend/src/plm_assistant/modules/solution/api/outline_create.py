"""Opt-in frozen SOL_OUTLINE_CREATE HTTP boundary."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.api.reference_create import _read_body, _uuid
from plm_assistant.modules.solution.application.create_outline import (
    CreateOutline, OutlineCreateError, OutlineCreateService, OutlineInitialView,
)


def _failure(error: OutlineCreateError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(view: OutlineInitialView, project: uuid.UUID) -> dict[str, object]:
    if (type(view) is not OutlineInitialView
            or view.project_id != project
            or type(view.solution_outline_id) is not uuid.UUID
            or view.solution_outline_id.int == 0
            or type(view.name) is not str or not view.name
            or type(view.created_at) is not datetime
            or view.created_at.tzinfo is None or view.created_at.utcoffset() is None
            or view.outline_state != "ACTIVE"
            or view.current_approved_version_ref is not None
            or view.etag != '"v0"'):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "solution_outline_id": str(view.solution_outline_id),
        "project_id": str(project), "name": view.name,
        "outline_state": "ACTIVE", "current_approved_version_ref": None,
        "created_at": view.created_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
        "etag": view.etag,
    }


def create_outline_create_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    creates: OutlineCreateService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, creates)):
        raise ValueError("SolutionOutline HTTP dependencies are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/solution-outlines")
    async def create(project_id: str, request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf = _session_cookie(headers), _csrf_header(headers)
        try:
            await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True)
        except SessionError as error:
            raise _session_failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        key, project = _idempotency_header(headers), _uuid(project_id)
        body = await _read_body(request, headers)
        if type(body) is not dict or set(body) != {"name"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["name"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        trace = uuid.UUID(request.state.trace_id)
        try:
            view = await run_in_threadpool(creates.create, CreateOutline(
                token, csrf, trace, project, body["name"], key))
        except OutlineCreateError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = _response(view, project)
        location = f"/api/v1/projects/{project}/solution-outlines/{view.solution_outline_id}"
        return JSONResponse(
            {"data": data, "trace_id": str(trace)}, status_code=201,
            headers={"Cache-Control": "no-store", "ETag": view.etag,
                     "Location": location},
        )

    return router
