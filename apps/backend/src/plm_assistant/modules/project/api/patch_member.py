"""Opt-in ProjectMember assignment PATCH with strong version precondition."""

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
from plm_assistant.modules.project.api.create_project import _canonical_uuid, _read_json
from plm_assistant.modules.project.api.read_members import _public
from plm_assistant.modules.project.application.patch_member import (
    PatchProjectMember, ProjectMemberPatchError, ProjectMemberPatchService,
)
from plm_assistant.modules.project.application.read_members import ProjectMemberView


def _error(exc: ProjectMemberPatchError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "PROJECT_ROLE_INVALID": "PROJECT_ROLE_INVALID",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE"))


def create_project_member_patch_router(*, sessions: SessionService,
                                       members: ProjectMemberPatchService,
                                       origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or members is None or origins is None:
        raise ValueError("session, member patch service and origins are required")
    router = APIRouter()

    @router.patch("/api/v1/projects/{project_id}/members/{project_member_id}")
    async def patch_member(project_id: uuid.UUID, project_member_id: uuid.UUID,
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
        if project_id.int == 0 or project_member_id.int == 0:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        body = await _read_json(request, headers)
        if (type(body) is not dict or not body
                or set(body) - {"role", "department_id"}):
            raise ApplicationError("REQUEST_MALFORMED")
        if "role" in body and type(body["role"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        command = PatchProjectMember(
            token, csrf, uuid.UUID(request.state.trace_id), project_id,
            project_member_id, expected_version,
            role=body.get("role"),
            department_id=(_canonical_uuid(body["department_id"])
                           if "department_id" in body else None),
        )
        try:
            view = await run_in_threadpool(members.patch, command)
        except ProjectMemberPatchError as exc:
            raise _error(exc) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not ProjectMemberView:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _public(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    return router
