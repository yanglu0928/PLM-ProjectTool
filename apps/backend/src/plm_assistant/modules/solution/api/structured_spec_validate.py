"""Opt-in frozen SOL_SPEC_VALIDATE HTTP boundary; no runtime wiring here."""

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
from plm_assistant.modules.solution.api.reference_create import _uuid
from plm_assistant.modules.solution.application.structured_spec_validation_contract import (
    StructuredSpecValidationReport, ValidateStructuredSpec,
)
from plm_assistant.modules.solution.application.validate_structured_spec import (
    StructuredSpecValidationError, StructuredSpecValidationService,
)


def _failure(error: StructuredSpecValidationError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(
    report: StructuredSpecValidationReport, *, project: uuid.UUID,
    spec: uuid.UUID,
) -> dict[str, object]:
    if (type(report) is not StructuredSpecValidationReport
            or (report.project_id,
                report.structured_solution_spec_id) != (project, spec)
            or type(report.observed_at) is not datetime
            or report.observed_at.tzinfo is None
            or report.observed_at.utcoffset() is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "audit_event_id": str(report.audit_event_id),
        "observation_trace_id": str(report.trace_id),
        "project_id": str(project),
        "structured_solution_spec_id": str(spec),
        "spec_series_id": str(report.spec_series_id),
        "spec_type": report.spec_type,
        "version_no": report.version_no,
        "version_state": report.version_state,
        "content_fingerprint": report.content_fingerprint.hex(),
        "payload_fingerprint": report.payload_fingerprint.hex(),
        "requirement_count": report.requirement_count,
        "section_count": report.section_count,
        "evidence_count": report.evidence_count,
        "artifact_count": report.artifact_count,
        "facts": {
            name: getattr(report.facts, name) for name in (
                "integrity", "payload", "requirements", "sections",
                "evidence", "artifacts", "trace", "current_version")
        },
        "type_checks": [
            {"code": item.code, "status": item.status}
            for item in report.type_checks.checks
        ],
        "valid": report.valid,
        "ready_for_review": report.ready_for_review,
        "issue_codes": list(report.issue_codes),
        "observed_at": report.observed_at.astimezone(
            timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def create_structured_spec_validate_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    validations: StructuredSpecValidationService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, validations)):
        raise ValueError("StructuredSpec validation HTTP dependencies required")
    router = APIRouter()

    @router.post(
        "/api/v1/projects/{project_id}/structured-solution-specs/"
        "{spec_id}:validate")
    async def validate(project_id: str, spec_id: str,
                       request: Request) -> JSONResponse:
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
        project, spec = _uuid(project_id), _uuid(spec_id)
        async for chunk in request.stream():
            if chunk:
                raise ApplicationError("REQUEST_MALFORMED")
        trace = uuid.UUID(request.state.trace_id)
        try:
            report = await run_in_threadpool(
                validations.validate, ValidateStructuredSpec(
                    token, csrf, trace, project, spec, key))
        except StructuredSpecValidationError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": _response(report, project=project, spec=spec),
             "trace_id": str(trace)},
            status_code=200, headers={"Cache-Control": "no-store"})

    return router
