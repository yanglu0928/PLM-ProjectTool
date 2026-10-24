"""Opt-in PROJECT/GLOBAL Reference human eligibility HTTP contract."""

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
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.application.set_reference_eligibility import (
    ReferenceEligibilityCommandError, ReferenceEligibilityResult,
    ReferenceEligibilityService, SetReferenceEligibility,
)

from .reference_create import _read_body, _uuid


_FIELDS = frozenset({"eligibility_state", "reason"})


def _failure(error: ReferenceEligibilityCommandError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "VERSION_CONFLICT": "CONFLICT_VERSION",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "SOURCE_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(result: ReferenceEligibilityResult, *,
              command: SetReferenceEligibility) -> tuple[dict[str, object], str]:
    if (type(result) is not ReferenceEligibilityResult
            or result.reference_solution_id != command.reference_solution_id
            or result.scope != command.scope or result.project_id != command.project_id
            or type(result.eligibility_event_id) is not uuid.UUID
            or result.eligibility_event_id.int == 0
            or type(result.reference_version_id) is not uuid.UUID
            or result.reference_version_id.int == 0
            or result.eligibility_state != command.requested_state
            or result.eligibility_reason != command.reason
            or type(result.result_lock_version) is not int
            or result.result_lock_version != command.expected_lock_version+1):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    etag = result.etag
    if etag != f'"v{result.result_lock_version}"':
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return ({
        "eligibility_event_id": str(result.eligibility_event_id),
        "reference_solution_id": str(result.reference_solution_id),
        "reference_version_id": str(result.reference_version_id),
        "scope": result.scope,
        "project_id": str(result.project_id) if result.project_id else None,
        "eligibility_state": result.eligibility_state,
        "eligibility_reason": result.eligibility_reason,
        "etag": etag,
    }, etag)


def _router(*, scope: str, sessions: SessionService,
            origins: LoginOriginPolicy,
            eligibility: ReferenceEligibilityService) -> APIRouter:
    if scope not in ("PROJECT", "GLOBAL") or any(
            value is None for value in (sessions, origins, eligibility)):
        raise ValueError("Reference eligibility HTTP dependencies required")
    router = APIRouter()

    async def set_eligibility(request: Request, identity_raw: str,
                              project_raw: str | None = None) -> JSONResponse:
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
        expected = parse_if_match(headers)
        key = _idempotency_header(headers)
        identity = _uuid(identity_raw)
        project = _uuid(project_raw) if project_raw is not None else None
        body = await _read_body(request, headers)
        if type(body) is not dict or set(body) != _FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        if (type(body["eligibility_state"]) is not str
                or type(body["reason"]) is not str):
            raise ApplicationError("VALIDATION_FAILED")
        trace = uuid.UUID(request.state.trace_id)
        command = SetReferenceEligibility(
            token, csrf, trace, scope, project, identity, expected,
            body["eligibility_state"], body["reason"], key)
        try:
            result = await run_in_threadpool(eligibility.set, command)
        except ReferenceEligibilityCommandError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data, etag = _response(result, command=command)
        return JSONResponse(
            {"data": data, "trace_id": str(trace)}, status_code=200,
            headers={"Cache-Control": "no-store", "ETag": etag})

    if scope == "PROJECT":
        @router.post("/api/v1/projects/{project_id}/reference-solutions/"
                     "{reference_solution_id}:set-eligibility")
        async def project_set(project_id: str, reference_solution_id: str,
                              request: Request) -> JSONResponse:
            return await set_eligibility(request, reference_solution_id, project_id)
    else:
        @router.post("/api/v1/global/reference-solutions/"
                     "{reference_solution_id}:set-eligibility")
        async def global_set(reference_solution_id: str,
                             request: Request) -> JSONResponse:
            return await set_eligibility(request, reference_solution_id)
    return router


def create_project_reference_eligibility_router(*, sessions: SessionService,
                                                origins: LoginOriginPolicy,
                                                eligibility: ReferenceEligibilityService) -> APIRouter:
    return _router(scope="PROJECT", sessions=sessions, origins=origins,
                   eligibility=eligibility)


def create_global_reference_eligibility_router(*, sessions: SessionService,
                                               origins: LoginOriginPolicy,
                                               eligibility: ReferenceEligibilityService) -> APIRouter:
    return _router(scope="GLOBAL", sessions=sessions, origins=origins,
                   eligibility=eligibility)
