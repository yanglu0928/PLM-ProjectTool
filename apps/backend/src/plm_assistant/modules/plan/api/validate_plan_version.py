"""Opt-in frozen PLAN_VERSION_VALIDATE HTTP boundary."""

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
from ._request import canonical_uuid
from plm_assistant.modules.plan.application.validate_plan_version import (
    PlanVersionValidationError, PlanVersionValidationService,
    ValidatePlanVersion,
)
from plm_assistant.modules.plan.application.validate_plan_version_contract import (
    PlanVersionCoverageSummary, PlanVersionValidationReport,
)


def _failure(error: PlanVersionValidationError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(report: PlanVersionValidationReport) -> dict[str, object]:
    if (type(report) is not PlanVersionValidationReport
            or type(report.coverage_summary) is not PlanVersionCoverageSummary
            or type(report.checked_at) is not datetime
            or report.checked_at.tzinfo is None
            or report.checked_at.utcoffset() is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    coverage = report.coverage_summary
    return {
        "valid": report.valid,
        "blocking_issues": list(report.blocking_issues),
        "warnings": list(report.warnings),
        "coverage_summary": {
            name: getattr(coverage, name) for name in (
                "requirement_total", "requirement_mapped",
                "requirement_excluded", "requirement_uncovered",
                "solution_total", "solution_mapped",
                "solution_excluded", "solution_uncovered",
            )
        },
        "checked_at": report.checked_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
    }


def create_plan_version_validate_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    validations: PlanVersionValidationService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, validations)):
        raise ValueError("PlanVersion validation HTTP dependencies are required")
    router = APIRouter()

    @router.post(
        "/api/v1/projects/{project_id}/plans/{plan_id}/versions/"
        "{plan_version_id}:validate")
    async def validate(project_id: str, plan_id: str,
                       plan_version_id: str, request: Request) -> JSONResponse:
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
        project, plan, version = (
            canonical_uuid(project_id), canonical_uuid(plan_id),
            canonical_uuid(plan_version_id))
        async for chunk in request.stream():
            if chunk:
                raise ApplicationError("REQUEST_MALFORMED")
        trace = uuid.UUID(request.state.trace_id)
        try:
            report = await run_in_threadpool(
                validations.validate,
                ValidatePlanVersion(token, csrf, trace, project, plan, version, key))
        except PlanVersionValidationError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": _response(report), "trace_id": str(trace)},
            status_code=200, headers={"Cache-Control": "no-store"})

    return router
