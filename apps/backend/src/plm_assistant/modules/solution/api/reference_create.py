"""Opt-in PROJECT ReferenceSolution create HTTP contract."""

from __future__ import annotations

import json
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
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.application.create_reference_solution import (
    CreateReferenceSolution, ReferenceCreateError, ReferenceCreateService,
    ReferenceInitialView,
)
from plm_assistant.modules.solution.application.reference_source_qualification import ReferenceSourceRequest


_MAX_BODY = 128 * 1024
_FIELDS = frozenset({
    "name", "document_version_ids", "evidence_ids", "source_project_class",
    "deidentification_class", "applicability",
})


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("nonstandard JSON constant")


async def _read_body(request: Request, headers: tuple[tuple[bytes, bytes], ...]) -> object:
    values = [value for name, value in headers if name.lower() == b"content-type"]
    if (len(values) != 1 or values[0].strip().lower() not in (
            b"application/json", b"application/json; charset=utf-8")):
        raise ApplicationError("REQUEST_MALFORMED")
    raw = bytearray()
    try:
        async for chunk in request.stream():
            if len(raw) + len(chunk) > _MAX_BODY:
                raise ApplicationError("REQUEST_MALFORMED")
            raw.extend(chunk)
        try:
            return json.loads(raw.decode("utf-8", errors="strict"),
                              object_pairs_hook=_unique_pairs,
                              parse_constant=_reject_constant)
        except (UnicodeDecodeError, ValueError, TypeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
    finally:
        raw[:] = b"\x00" * len(raw)


def _uuid(value: object) -> uuid.UUID:
    if type(value) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ApplicationError("VALIDATION_FAILED") from None
    if parsed.int == 0 or str(parsed) != value:
        raise ApplicationError("VALIDATION_FAILED")
    return parsed


def _ids(value: object) -> tuple[uuid.UUID, ...]:
    if type(value) is not list:
        raise ApplicationError("VALIDATION_FAILED")
    return tuple(_uuid(item) for item in value)


def _failure(error: ReferenceCreateError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "SOURCE_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(view: ReferenceInitialView, project: uuid.UUID) -> dict[str, object]:
    if (type(view) is not ReferenceInitialView
            or view.scope != "PROJECT" or view.project_id != project
            or view.deidentification_confirmation_id is not None
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                view.reference_solution_id, view.reference_version_id, view.created_by))
            or type(view.name) is not str or not view.name
            or type(view.created_at) is not datetime or view.created_at.tzinfo is None
            or view.created_at.utcoffset() is None
            or view.eligibility_state != "REFERENCE_ONLY"
            or view.version_state != "DRAFT" or view.etag != '"v0"'):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "reference_solution_id": str(view.reference_solution_id),
        "reference_version_id": str(view.reference_version_id),
        "scope": "PROJECT", "project_id": str(project), "name": view.name,
        "eligibility_state": view.eligibility_state,
        "version_state": view.version_state,
        "created_by": str(view.created_by),
        "created_at": view.created_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
        "etag": view.etag,
    }


def create_project_reference_create_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    creates: ReferenceCreateService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, creates)):
        raise ValueError("PROJECT Reference HTTP dependencies are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/reference-solutions")
    async def create(project_id: str, request: Request) -> JSONResponse:
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
        key, project = _idempotency_header(headers), _uuid(project_id)
        body = await _read_body(request, headers)
        if type(body) is not dict or set(body) != _FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        if (type(body["name"]) is not str
                or type(body["source_project_class"]) is not str
                or type(body["deidentification_class"]) is not str
                or type(body["applicability"]) is not dict):
            raise ApplicationError("VALIDATION_FAILED")
        trace = uuid.UUID(request.state.trace_id)
        sources = ReferenceSourceRequest(
            token, trace, "PROJECT", project,
            _ids(body["document_version_ids"]), _ids(body["evidence_ids"]),
            body["source_project_class"], body["deidentification_class"],
            body["applicability"],
        )
        try:
            view = await run_in_threadpool(creates.create,
                CreateReferenceSolution(sources, csrf, body["name"], key))
        except ReferenceCreateError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = _response(view, project)
        location = (f"/api/v1/projects/{project}/reference-solutions/"
                    f"{view.reference_solution_id}")
        return JSONResponse({"data": data, "trace_id": str(trace)},
            status_code=201, headers={"Cache-Control": "no-store",
                                      "ETag": view.etag, "Location": location})

    return router
