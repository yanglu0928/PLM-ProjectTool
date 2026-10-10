"""Opt-in Project Department create HTTP; authorization remains in Project."""

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
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.project.api.create_project import _read_json
from plm_assistant.modules.project.api.read_departments import _public
from plm_assistant.modules.project.application.create_department import (
    CreateProjectDepartment, ProjectDepartmentCreateError, ProjectDepartmentCreateService,
)
from plm_assistant.modules.project.application.read_departments import DepartmentView


def _command(body: object, *, token: bytes, csrf: bytes, trace_id: uuid.UUID,
             project_id: uuid.UUID) -> CreateProjectDepartment:
    if type(body) is not dict or set(body) != {"code", "name"}:
        raise ApplicationError("REQUEST_MALFORMED")
    if type(body["code"]) is not str or type(body["name"]) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    return CreateProjectDepartment(
        token, csrf, trace_id, project_id, body["code"], body["name"],
    )


def _error(exc: ProjectDepartmentCreateError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "CONFLICT_DUPLICATE": "CONFLICT_DUPLICATE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE"))


def create_project_department_create_router(*, sessions: SessionService,
                                            departments: ProjectDepartmentCreateService,
                                            origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or departments is None or origins is None:
        raise ValueError("session, department create service and origins are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/departments")
    async def create_department(project_id: uuid.UUID, request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf, key = (
            _session_cookie(headers), _csrf_header(headers), _idempotency_header(headers),
        )
        try:
            await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True,
            )
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if project_id.int == 0:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        body = await _read_json(request, headers)
        command = _command(body, token=token, csrf=csrf,
                           trace_id=uuid.UUID(request.state.trace_id), project_id=project_id)
        try:
            view = await run_in_threadpool(
                departments.create_idempotent, command, idempotency_key=key,
            )
        except ProjectDepartmentCreateError as exc:
            raise _error(exc) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not DepartmentView or view.state != "ACTIVE" or view.etag != '"v0"':
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": _public(view), "trace_id": request.state.trace_id},
                            status_code=201, headers={
                                "Cache-Control": "no-store", "ETag": view.etag,
                                "Location": f"/api/v1/projects/{project_id}/departments/{view.department_id}",
                            })

    return router
