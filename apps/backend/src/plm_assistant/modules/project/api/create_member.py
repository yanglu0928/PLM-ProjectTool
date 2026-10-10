"""Opt-in ProjectMember create HTTP; business authorization stays in Project."""

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
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.project.api.create_project import _canonical_uuid, _read_json
from plm_assistant.modules.project.api.read_members import _public
from plm_assistant.modules.project.application.create_member import (
    CreateProjectMember, ProjectMemberCreateError, ProjectMemberCreateService,
)
from plm_assistant.modules.project.application.read_members import ProjectMemberView


def _effective_at(value: object) -> datetime:
    if type(value) is not str or not value or len(value) > 40:
        raise ApplicationError("VALIDATION_FAILED")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ApplicationError("VALIDATION_FAILED") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise ApplicationError("VALIDATION_FAILED")
    return parsed.astimezone(timezone.utc)


def _command(body: object, *, token: bytes, csrf: bytes, trace_id: uuid.UUID,
             project_id: uuid.UUID) -> CreateProjectMember:
    if (type(body) is not dict
            or not {"user_id", "role", "department_id"}.issubset(body)
            or set(body) - {"user_id", "role", "department_id", "effective_at"}):
        raise ApplicationError("REQUEST_MALFORMED")
    if type(body["role"]) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    return CreateProjectMember(
        token, csrf, trace_id, project_id,
        _canonical_uuid(body["user_id"]), body["role"],
        _canonical_uuid(body["department_id"]),
        _effective_at(body["effective_at"]) if "effective_at" in body else None,
    )


def _error(exc: ProjectMemberCreateError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "PROJECT_ROLE_INVALID": "PROJECT_ROLE_INVALID",
        "PROJECT_USER_ALREADY_ASSIGNED": "PROJECT_USER_ALREADY_ASSIGNED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE"))


def create_project_member_create_router(*, sessions: SessionService,
                                        members: ProjectMemberCreateService,
                                        origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or members is None or origins is None:
        raise ValueError("session, member create service and origins are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/members")
    async def create_member(project_id: uuid.UUID, request: Request) -> JSONResponse:
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
                members.create_idempotent, command, idempotency_key=key,
            )
        except ProjectMemberCreateError as exc:
            raise _error(exc) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not ProjectMemberView or view.state != "ACTIVE" or view.etag != '"v0"':
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = _public(view)
        return JSONResponse({"data": data, "trace_id": request.state.trace_id},
                            status_code=201, headers={
                                "Cache-Control": "no-store", "ETag": view.etag,
                                "Location": f"/api/v1/projects/{project_id}/members/{view.member_id}",
                            })

    return router
