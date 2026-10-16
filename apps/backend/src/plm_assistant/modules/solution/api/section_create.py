"""Opt-in frozen SOL_SECTION_CREATE HTTP boundary."""

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
from plm_assistant.modules.solution.application.create_section import (
    CreateSection, SectionCreateError, SectionCreateService, SectionInitialView,
)


def _failure(error: SectionCreateError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_DUPLICATE": "CONFLICT_DUPLICATE",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(view: SectionInitialView, project: uuid.UUID) -> dict[str, object]:
    if (type(view) is not SectionInitialView or view.project_id != project
            or type(view.solution_section_id) is not uuid.UUID
            or view.solution_section_id.int == 0
            or type(view.solution_outline_id) is not uuid.UUID
            or view.solution_outline_id.int == 0
            or type(view.section_key) is not str or not view.section_key
            or type(view.created_at) is not datetime
            or view.created_at.tzinfo is None or view.created_at.utcoffset() is None
            or view.section_state != "ACTIVE"
            or view.current_approved_version_ref is not None
            or view.etag != '"v0"'):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "solution_section_id": str(view.solution_section_id),
        "solution_outline_id": str(view.solution_outline_id),
        "project_id": str(project), "section_key": view.section_key,
        "section_state": "ACTIVE", "current_approved_version_ref": None,
        "created_at": view.created_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
        "etag": view.etag,
    }


def create_section_create_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    creates: SectionCreateService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, creates)):
        raise ValueError("SolutionSection HTTP dependencies are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/solution-sections")
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
        if type(body) is not dict or set(body) != {"solution_outline_id", "section_key"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["section_key"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        outline = _uuid(body["solution_outline_id"])
        trace = uuid.UUID(request.state.trace_id)
        try:
            view = await run_in_threadpool(creates.create, CreateSection(
                token, csrf, trace, project, outline, body["section_key"], key))
        except SectionCreateError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = _response(view, project)
        location = f"/api/v1/projects/{project}/solution-sections/{view.solution_section_id}"
        return JSONResponse(
            {"data": data, "trace_id": str(trace)}, status_code=201,
            headers={"Cache-Control": "no-store", "ETag": view.etag,
                     "Location": location},
        )

    return router
