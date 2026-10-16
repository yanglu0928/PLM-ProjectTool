"""Opt-in GLOBAL Reference detail read; no cross-project or confirmation claim."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.api.reference_read import _timestamp, _uuid
from plm_assistant.modules.solution.application.read_global_reference import (
    GlobalReferenceCurrentView, GlobalReferenceReadError, GlobalReferenceReadQuery,
    GlobalReferenceReadService,
)


def _public(view: GlobalReferenceCurrentView, identity: uuid.UUID) -> dict[str, object]:
    if (type(view) is not GlobalReferenceCurrentView
            or view.reference_solution_id != identity):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "reference_solution_id": str(view.reference_solution_id),
        "reference_version_id": str(view.reference_version_id),
        "scope": "GLOBAL", "project_id": None,
        "name": view.name,
        "eligibility_state": view.eligibility_state,
        "eligibility_reason": view.eligibility_reason,
        "version_no": view.version_no,
        "version_state": view.version_state,
        "source_project_class": view.source_project_class,
        "deidentification_class": view.deidentification_class,
        "applicability": view.applicability,
        "document_version_ids": [str(ref.document_version_id)
                                 for ref in view.document_refs],
        "document_refs": [{"document_id": str(ref.document_id),
                           "document_version_id": str(ref.document_version_id)}
                          for ref in view.document_refs],
        "evidence_ids": [str(item) for item in view.evidence_ids],
        "source_fingerprint": view.source_fingerprint.hex(),
        "content_fingerprint": view.content_fingerprint.hex(),
        "created_by": str(view.created_by),
        "created_at": _timestamp(view.created_at),
        "version_created_by": str(view.version_created_by),
        "version_created_at": _timestamp(view.version_created_at),
        "etag": view.etag,
    }


def _failure(error: GlobalReferenceReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def create_global_reference_read_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: GlobalReferenceReadService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads)):
        raise ValueError("GLOBAL Reference read dependencies required")
    router = APIRouter()

    @router.get("/api/v1/global/reference-solutions/{reference_solution_id}")
    async def get(reference_solution_id: str, request: Request) -> JSONResponse:
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
        identity = _uuid(reference_solution_id)
        trace = uuid.UUID(request.state.trace_id)
        try:
            view = await run_in_threadpool(
                reads.get_current, GlobalReferenceReadQuery(token, trace), identity)
        except GlobalReferenceReadError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({"data": _public(view, identity), "trace_id": str(trace)},
                            headers={"Cache-Control": "no-store", "ETag": view.etag})

    return router
