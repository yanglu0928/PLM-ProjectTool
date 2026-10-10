"""Opt-in DeploymentAdmin command for reviewed GLOBAL candidate visibility."""

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
from plm_assistant.modules.solution.application.set_global_reference_publication import (
    GlobalReferencePublicationError, GlobalReferencePublicationResult,
    GlobalReferencePublicationService, SetGlobalReferencePublication,
)

from .reference_create import _read_body, _uuid


_FIELDS = frozenset({
    "reference_version_id", "expected_event_no", "event_kind",
    "display_label", "reason",
})


def _failure(error: GlobalReferencePublicationError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "VERSION_CONFLICT": "CONFLICT_VERSION",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "SOURCE_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(result: GlobalReferencePublicationResult, *,
              command: SetGlobalReferencePublication) -> dict[str, object]:
    if (type(result) is not GlobalReferencePublicationResult
            or type(result.publication_event_id) is not uuid.UUID
            or result.publication_event_id.int == 0
            or result.reference_solution_id != command.reference_solution_id
            or result.reference_version_id != command.expected_reference_version_id
            or result.event_no != command.expected_event_no + 1
            or result.event_kind != command.event_kind
            or result.display_label != command.display_label
            or result.reason != command.reason
            or type(result.created_at) is not datetime
            or result.created_at.tzinfo is None
            or result.created_at.utcoffset() is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "publication_event_id": str(result.publication_event_id),
        "reference_solution_id": str(result.reference_solution_id),
        "reference_version_id": str(result.reference_version_id),
        "event_no": result.event_no,
        "event_kind": result.event_kind,
        "display_label": result.display_label,
        "reason": result.reason,
        "created_at": result.created_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
    }


def create_global_reference_publication_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    publication: GlobalReferencePublicationService,
) -> APIRouter:
    if any(part is None for part in (sessions, origins, publication)):
        raise ValueError("GLOBAL Reference publication HTTP dependencies required")
    router = APIRouter()

    @router.post("/api/v1/global/reference-solutions/"
                 "{reference_solution_id}:set-candidate-publication")
    async def set_publication(reference_solution_id: str,
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
        key, root = _idempotency_header(headers), _uuid(reference_solution_id)
        body = await _read_body(request, headers)
        if type(body) is not dict or set(body) != _FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        if (type(body["expected_event_no"]) is not int
                or type(body["event_kind"]) is not str
                or body["display_label"] is not None
                and type(body["display_label"]) is not str
                or type(body["reason"]) is not str):
            raise ApplicationError("VALIDATION_FAILED")
        trace = uuid.UUID(request.state.trace_id)
        command = SetGlobalReferencePublication(
            token, csrf, trace, root, _uuid(body["reference_version_id"]),
            body["expected_event_no"], body["event_kind"],
            body["display_label"], body["reason"], key)
        try:
            result = await run_in_threadpool(publication.set, command)
        except GlobalReferencePublicationError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": _response(result, command=command), "trace_id": str(trace)},
            status_code=200, headers={"Cache-Control": "no-store"})

    return router
