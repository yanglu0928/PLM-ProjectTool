"""Opt-in PROJECT ReferenceSolution current-version GET HTTP contract."""

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
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.application.read_reference import (
    ReferenceCurrentView, ReferenceReadError, ReferenceReadQuery,
    ReferenceReadService,
)


def _uuid(raw: str) -> uuid.UUID:
    try:
        value = uuid.UUID(raw)
    except (TypeError, ValueError, AttributeError):
        raise ApplicationError("RESOURCE_NOT_FOUND") from None
    if value.int == 0 or str(value) != raw:
        raise ApplicationError("RESOURCE_NOT_FOUND")
    return value


def _timestamp(value: datetime) -> str:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _response(view: ReferenceCurrentView, project: uuid.UUID,
              identity: uuid.UUID) -> dict[str, object]:
    if (type(view) is not ReferenceCurrentView
            or view.project_id != project
            or view.reference_solution_id != identity
            or view.scope != "PROJECT"):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "reference_solution_id": str(view.reference_solution_id),
        "reference_version_id": str(view.reference_version_id),
        "scope": "PROJECT", "project_id": str(project),
        "name": view.name,
        "eligibility_state": view.eligibility_state,
        "eligibility_reason": view.eligibility_reason,
        "version_no": view.version_no,
        "version_state": view.version_state,
        "source_project_class": view.source_project_class,
        "deidentification_class": view.deidentification_class,
        "applicability": view.applicability,
        "document_version_ids": [str(item) for item in view.document_version_ids],
        "evidence_ids": [str(item) for item in view.evidence_ids],
        "source_fingerprint": view.source_fingerprint.hex(),
        "content_fingerprint": view.content_fingerprint.hex(),
        "created_by": str(view.created_by),
        "created_at": _timestamp(view.created_at),
        "version_created_by": str(view.version_created_by),
        "version_created_at": _timestamp(view.version_created_at),
        "etag": view.etag,
    }


def _failure(error: ReferenceReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def create_project_reference_read_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: ReferenceReadService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads)):
        raise ValueError("PROJECT Reference read dependencies required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/reference-solutions/{reference_solution_id}")
    async def get(project_id: str, reference_solution_id: str,
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
        project, identity = _uuid(project_id), _uuid(reference_solution_id)
        trace = uuid.UUID(request.state.trace_id)
        try:
            view = await run_in_threadpool(
                reads.get_current, ReferenceReadQuery(token, trace, project), identity)
        except ReferenceReadError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = _response(view, project, identity)
        return JSONResponse({"data": data, "trace_id": str(trace)},
                            headers={"Cache-Control": "no-store", "ETag": view.etag})

    return router
