"""Opt-in frozen PlanVersion DRAFT creation HTTP boundary."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import (
    SessionError, SessionService,
)
from plm_assistant.modules.platform.application.errors import ApplicationError
from ._request import canonical_uuid, read_body
from plm_assistant.modules.plan.application.create_plan_version import (
    CreatePlanVersion, PlanVersionCreateError, PlanVersionCreateService,
    PlanVersionCreatedView,
)


def _failure(error: PlanVersionCreateError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "PLAN_SOURCE_UNAVAILABLE": "RESOURCE_NOT_FOUND",
        "OUTPUT_REFERENCE_UNAVAILABLE": "VALIDATION_FAILED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(view: PlanVersionCreatedView, *, project: uuid.UUID,
              plan: uuid.UUID) -> dict[str, object]:
    if (type(view) is not PlanVersionCreatedView
            or view.project_id != project or view.plan_id != plan
            or type(view.plan_version_id) is not uuid.UUID
            or view.plan_version_id.int == 0
            or type(view.version_no) is not int or view.version_no < 1
            or view.version_state != "DRAFT"
            or type(view.created_at) is not datetime
            or view.created_at.tzinfo is None or view.created_at.utcoffset() is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "plan_version_id": str(view.plan_version_id),
        "plan_id": str(plan), "project_id": str(project),
        "version_no": view.version_no, "version_state": "DRAFT",
        "created_at": view.created_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
    }


def create_plan_version_create_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    creates: PlanVersionCreateService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, creates)):
        raise ValueError("PlanVersion HTTP dependencies are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/plans/{plan_id}/versions")
    async def create(project_id: str, plan_id: str, request: Request) -> JSONResponse:
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
        key = _idempotency_header(headers)
        project, plan = canonical_uuid(project_id), canonical_uuid(plan_id)
        body = await read_body(request, headers, maximum_bytes=8 * 1024 * 1024)
        if type(body) is not dict:
            raise ApplicationError("REQUEST_MALFORMED")
        trace = uuid.UUID(request.state.trace_id)
        try:
            view = await run_in_threadpool(creates.create, CreatePlanVersion(
                token, csrf, trace, project, plan, body, key))
        except PlanVersionCreateError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = _response(view, project=project, plan=plan)
        location = (f"/api/v1/projects/{project}/plans/{plan}/versions/"
                    f"{view.plan_version_id}")
        return JSONResponse(
            {"data": data, "trace_id": str(trace)}, status_code=201,
            headers={"Cache-Control": "no-store", "Location": location},
        )

    return router
