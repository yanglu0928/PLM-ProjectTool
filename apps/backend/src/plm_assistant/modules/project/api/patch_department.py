"""Opt-in Project Department PATCH with a strong version precondition."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _csrf_header, _session_cookie, _session_failure
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.project.api.create_project import _read_json
from plm_assistant.modules.project.api.read_departments import _public
from plm_assistant.modules.project.application.patch_department import (
    PatchProjectDepartment, ProjectDepartmentPatchError, ProjectDepartmentPatchService,
)
from plm_assistant.modules.project.application.read_departments import DepartmentView


def _error(exc: ProjectDepartmentPatchError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "CONFLICT_DUPLICATE": "CONFLICT_DUPLICATE",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE"))


def create_project_department_patch_router(*, sessions: SessionService,
                                           departments: ProjectDepartmentPatchService,
                                           origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or departments is None or origins is None:
        raise ValueError("session, department patch service and origins are required")
    router = APIRouter()

    @router.patch("/api/v1/projects/{project_id}/departments/{department_id}")
    async def patch_department(project_id: uuid.UUID, department_id: uuid.UUID,
                               request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf = _session_cookie(headers), _csrf_header(headers)
        try:
            await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True,
            )
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        expected_version = parse_if_match(headers)
        if project_id.int == 0 or department_id.int == 0:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        body = await _read_json(request, headers)
        if type(body) is not dict or not body or set(body) - {"code", "name"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if any(type(value) is not str for value in body.values()):
            raise ApplicationError("VALIDATION_FAILED")
        command = PatchProjectDepartment(
            token, csrf, uuid.UUID(request.state.trace_id), project_id,
            department_id, expected_version,
            code=body.get("code"), name=body.get("name"),
        )
        try:
            view = await run_in_threadpool(departments.patch, command)
        except ProjectDepartmentPatchError as exc:
            raise _error(exc) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not DepartmentView:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _public(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    return router
