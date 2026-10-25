"""Opt-in frozen PLAN_VERSION_GET HTTP boundary."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import (
    SessionError, SessionService,
)
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.plan.application.read_plan_version import (
    PlanVersionReadError, PlanVersionReadQuery, PlanVersionReadService,
    PlanVersionSnapshotView,
)
from ._request import canonical_uuid


_SNAPSHOT_KEYS = {
    "calendar_ref", "approved_solution_refs", "wbs_items", "dependencies",
    "milestones", "exclusions",
}


def _failure(error: PlanVersionReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(view: PlanVersionSnapshotView, *, project: uuid.UUID,
              plan: uuid.UUID, version: uuid.UUID) -> dict[str, object]:
    if (type(view) is not PlanVersionSnapshotView
            or view.project_id != project or view.plan_id != plan
            or view.plan_version_id != version
            or type(view.version_no) is not int or view.version_no < 1
            or view.version_state not in {
                "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED",
            }
            or type(view.created_by) is not uuid.UUID or view.created_by.int == 0
            or type(view.created_at) is not datetime
            or view.created_at.tzinfo is None or view.created_at.utcoffset() is None
            or any(value is not None and (
                type(value) is not uuid.UUID or value.int == 0
            ) for value in (view.supersedes_version_ref, view.review_ref,
                            view.review_round_ref))
            or type(view.snapshot) is not dict
            or set(view.snapshot) != _SNAPSHOT_KEYS
            or type(view.snapshot["approved_solution_refs"]) is not list
            or type(view.snapshot["wbs_items"]) is not list
            or type(view.snapshot["dependencies"]) is not list
            or type(view.snapshot["milestones"]) is not list
            or type(view.snapshot["exclusions"]) is not list):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "plan_version_id": str(version), "plan_id": str(plan),
        "project_id": str(project), "version_no": view.version_no,
        "version_state": view.version_state, "created_by": str(view.created_by),
        "supersedes_version_ref": (str(view.supersedes_version_ref)
                                   if view.supersedes_version_ref else None),
        "review_ref": str(view.review_ref) if view.review_ref else None,
        "review_round_ref": (str(view.review_round_ref)
                             if view.review_round_ref else None),
        "created_at": view.created_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
        **view.snapshot,
    }


def create_plan_version_read_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: PlanVersionReadService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads)):
        raise ValueError("PlanVersion read HTTP dependencies are required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}")
    async def get(project_id: str, plan_id: str, plan_version_id: str,
                  request: Request) -> JSONResponse:
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
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        project, plan, version = (canonical_uuid(value) for value in (
            project_id, plan_id, plan_version_id))
        trace = uuid.UUID(request.state.trace_id)
        try:
            view = await run_in_threadpool(
                reads.get_current,
                PlanVersionReadQuery(token, trace, project),
                plan_id=plan, plan_version_id=version,
            )
        except PlanVersionReadError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = _response(view, project=project, plan=plan, version=version)
        return JSONResponse(
            {"data": data, "trace_id": str(trace)},
            headers={"Cache-Control": "no-store"},
        )

    return router
