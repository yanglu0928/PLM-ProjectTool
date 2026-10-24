"""Opt-in frozen SOL_OUTLINE_VERSION_VALIDATE HTTP boundary."""

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
from plm_assistant.modules.solution.api.reference_create import _uuid
from plm_assistant.modules.solution.application.outline_version_validation_contract import (
    OutlineVersionValidationReport, ValidateOutlineVersion,
)
from plm_assistant.modules.solution.application.validate_outline_version import (
    OutlineVersionValidationError, OutlineVersionValidationService,
)


def _failure(error: OutlineVersionValidationError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(view: OutlineVersionValidationReport, *, project: uuid.UUID,
              outline: uuid.UUID, version: uuid.UUID) -> dict[str, object]:
    if (type(view) is not OutlineVersionValidationReport
            or (view.project_id, view.solution_outline_id,
                view.solution_outline_version_id) != (project, outline, version)
            or type(view.observed_at) is not datetime
            or view.observed_at.tzinfo is None
            or view.observed_at.utcoffset() is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "audit_event_id": str(view.audit_event_id),
        "observation_trace_id": str(view.trace_id),
        "project_id": str(project),
        "solution_outline_id": str(outline),
        "solution_outline_version_id": str(version),
        "version_no": view.version_no,
        "version_state": view.version_state,
        "content_fingerprint": view.content_fingerprint.hex(),
        "section_count": view.section_count,
        "requirement_count": view.requirement_count,
        "reference_count": view.reference_count,
        "facts": {
            name: getattr(view.facts, name) for name in (
                "order", "source", "coverage")
        },
        "valid": view.valid,
        "ready_for_review": view.ready_for_review,
        "issue_codes": list(view.issue_codes),
        "observed_at": view.observed_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
    }


def create_outline_version_validate_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    validations: OutlineVersionValidationService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, validations)):
        raise ValueError("OutlineVersion validation HTTP dependencies are required")
    router = APIRouter()

    @router.post(
        "/api/v1/projects/{project_id}/solution-outlines/{outline_id}"
        "/versions/{outline_version_id}:validate")
    async def validate(project_id: str, outline_id: str,
                       outline_version_id: str, request: Request) -> JSONResponse:
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
        project, outline, version = (
            _uuid(project_id), _uuid(outline_id), _uuid(outline_version_id))
        async for chunk in request.stream():
            if chunk:
                raise ApplicationError("REQUEST_MALFORMED")
        trace = uuid.UUID(request.state.trace_id)
        try:
            view = await run_in_threadpool(validations.validate,
                                           ValidateOutlineVersion(
                                               token, csrf, trace, project, outline,
                                               version, key))
        except OutlineVersionValidationError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": _response(view, project=project, outline=outline,
                               version=version),
             "trace_id": str(trace)},
            status_code=200, headers={"Cache-Control": "no-store"})

    return router
