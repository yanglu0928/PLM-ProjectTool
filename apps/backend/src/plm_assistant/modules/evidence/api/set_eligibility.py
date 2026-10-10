"""Opt-in human Evidence eligibility decision; absent from default application."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.evidence.application.set_eligibility import (
    EvidenceEligibilityCommandError, EvidenceEligibilityService,
    SetEvidenceEligibility, SetEvidenceEligibilityResult,
)
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.project.api.create_project import _read_json


def _error(error: EvidenceEligibilityCommandError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def create_evidence_eligibility_router(
        *, sessions: SessionService, origins: LoginOriginPolicy,
        service_factory: Callable[[bytes, bytes], EvidenceEligibilityService]) -> APIRouter:
    if any(item is None for item in (sessions, origins, service_factory)):
        raise ValueError("Evidence eligibility HTTP dependencies required")
    router = APIRouter()

    async def _set(request: Request, *, scope: str,
                   project_id: uuid.UUID | None,
                   evidence_id: uuid.UUID) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf, key = (_session_cookie(headers), _csrf_header(headers),
                            _idempotency_header(headers))
        try:
            principal = await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True,
            )
        except SessionError as error:
            raise _session_failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        actor_id = getattr(principal, "user_id", None)
        if type(actor_id) is not uuid.UUID or actor_id.int == 0:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        expected = parse_if_match(headers)
        if (evidence_id.int == 0 or scope == "PROJECT" and (
                type(project_id) is not uuid.UUID or project_id.int == 0)):
            raise ApplicationError("RESOURCE_NOT_FOUND")
        body = await _read_json(request, headers)
        if (type(body) is not dict or set(body) != {"eligibility_state", "reason"}
                or type(body["eligibility_state"]) is not str
                or type(body["reason"]) is not str):
            raise ApplicationError("REQUEST_MALFORMED")
        command = SetEvidenceEligibility(
            actor_id, token, csrf, uuid.UUID(request.state.trace_id), scope,
            project_id, evidence_id, expected, body["eligibility_state"], body["reason"],
        )
        try:
            service = service_factory(token, csrf)
            result = await run_in_threadpool(service.set, command,
                                             idempotency_key=key)
        except EvidenceEligibilityCommandError as error:
            raise _error(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not SetEvidenceEligibilityResult
                or result.evidence_id != evidence_id
                or result.eligibility_state not in ("ELIGIBLE", "INELIGIBLE")
                or result.eligibility_state != command.requested_state
                or result.eligibility_reason != command.reason
                or result.etag != f'"v{expected + 1}"'):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": {
            "evidence_id": str(result.evidence_id),
            "eligibility_state": result.eligibility_state,
            "eligibility_reason": result.eligibility_reason,
            "etag": result.etag,
        }, "trace_id": request.state.trace_id}, status_code=200,
            headers={"Cache-Control": "no-store", "ETag": result.etag})

    @router.post("/api/v1/global/evidence/{evidence_id}:set-eligibility")
    async def set_global(evidence_id: uuid.UUID, request: Request) -> JSONResponse:
        return await _set(request, scope="GLOBAL", project_id=None,
                          evidence_id=evidence_id)

    @router.post("/api/v1/projects/{project_id}/evidence/{evidence_id}:set-eligibility")
    async def set_project(project_id: uuid.UUID, evidence_id: uuid.UUID,
                          request: Request) -> JSONResponse:
        return await _set(request, scope="PROJECT", project_id=project_id,
                          evidence_id=evidence_id)

    return router
