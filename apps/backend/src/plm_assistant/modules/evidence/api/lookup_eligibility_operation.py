"""Optional read-only POST for an actor's Evidence eligibility receipt."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.evidence.application.lookup_eligibility_operation import (
    EvidenceEligibilityLookupError, EvidenceEligibilityOperationLookupService,
    EvidenceEligibilityOperationStatus, LookupEvidenceEligibilityOperation,
)
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, validate_idempotency_key,
)
from plm_assistant.modules.project.api.create_project import _read_json


def _error(error: EvidenceEligibilityLookupError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def create_evidence_eligibility_operation_lookup_router(
        *, sessions: SessionService, origins: LoginOriginPolicy,
        service_factory: Callable[[bytes, bytes], EvidenceEligibilityOperationLookupService]) -> APIRouter:
    if any(item is None for item in (sessions, origins, service_factory)):
        raise ValueError("Evidence eligibility lookup HTTP dependencies required")
    router = APIRouter()

    async def _lookup(request: Request, *, scope: str,
                      project_id: uuid.UUID | None,
                      evidence_id: uuid.UUID) -> JSONResponse:
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf = _session_cookie(headers), _csrf_header(headers)
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
        if evidence_id.int == 0 or scope == "PROJECT" and (
                type(project_id) is not uuid.UUID or project_id.int == 0):
            raise ApplicationError("RESOURCE_NOT_FOUND")
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != {"operation_key"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["operation_key"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(body["operation_key"])
        except IdempotencyError:
            raise ApplicationError("VALIDATION_FAILED") from None
        query = LookupEvidenceEligibilityOperation(
            actor_id, token, csrf, uuid.UUID(request.state.trace_id),
            scope, project_id, evidence_id, body["operation_key"],
        )
        try:
            service = service_factory(token, csrf)
            result = await run_in_threadpool(service.lookup, query)
        except EvidenceEligibilityLookupError as error:
            raise _error(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(result) is not EvidenceEligibilityOperationStatus:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        if result.status == "UNCONFIRMED" and result.evidence_id is None \
                and result.first_status_code is None:
            data = {"status": "UNCONFIRMED"}
        elif result.status == "COMPLETED" and result.evidence_id == evidence_id \
                and result.first_status_code == 200:
            data = {"status": "COMPLETED", "evidence_id": str(evidence_id),
                    "first_status_code": 200}
        else:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": data, "trace_id": request.state.trace_id},
                            headers={"Cache-Control": "no-store"})

    @router.post("/api/v1/global/evidence/{evidence_id}:lookup-eligibility-operation")
    async def lookup_global(evidence_id: uuid.UUID, request: Request) -> JSONResponse:
        return await _lookup(request, scope="GLOBAL", project_id=None,
                             evidence_id=evidence_id)

    @router.post("/api/v1/projects/{project_id}/evidence/{evidence_id}:lookup-eligibility-operation")
    async def lookup_project(project_id: uuid.UUID, evidence_id: uuid.UUID,
                             request: Request) -> JSONResponse:
        return await _lookup(request, scope="PROJECT", project_id=project_id,
                             evidence_id=evidence_id)

    return router
