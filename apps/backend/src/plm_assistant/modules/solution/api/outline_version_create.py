"""Opt-in frozen SOL_OUTLINE_VERSION_CREATE HTTP boundary."""

from __future__ import annotations

import json
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
from plm_assistant.modules.solution.api.reference_create import (
    _reject_constant, _unique_pairs, _uuid,
)
from plm_assistant.modules.solution.application.create_outline_version import (
    CreateOutlineVersion, OutlineVersionCreateError,
    OutlineVersionCreateService, OutlineVersionInitialView,
)
from plm_assistant.modules.solution.application.outline_version_input import (
    OutlineReferenceRef, OutlineRequirementRef, OutlineVersionDraftInput,
)


_MAX_BODY = 512 * 1024
_FIELDS = frozenset({
    "section_ids", "requirement_refs", "reference_refs",
    "missing_declarations", "conflict_declarations",
})


async def _body(request: Request, headers: tuple[tuple[bytes, bytes], ...]) -> object:
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
        except (UnicodeDecodeError, ValueError, TypeError, RecursionError):
            raise ApplicationError("REQUEST_MALFORMED") from None
    finally:
        raw[:] = b"\x00" * len(raw)


def _draft(body: object, project: uuid.UUID,
           outline: uuid.UUID) -> OutlineVersionDraftInput:
    if type(body) is not dict or set(body) != _FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    sections = body["section_ids"]
    requirements = body["requirement_refs"]
    references = body["reference_refs"]
    missing = body["missing_declarations"]
    conflicts = body["conflict_declarations"]
    if (type(sections) is not list or type(requirements) is not list
            or type(references) is not list or type(missing) is not list
            or type(conflicts) is not list
            or any(type(item) is not dict for item in (*missing, *conflicts))):
        raise ApplicationError("VALIDATION_FAILED")
    fixed_requirements = []
    for item in requirements:
        if type(item) is not dict or set(item) != {"requirement_id", "requirement_version_id"}:
            raise ApplicationError("VALIDATION_FAILED")
        fixed_requirements.append(OutlineRequirementRef(
            _uuid(item["requirement_id"]), _uuid(item["requirement_version_id"])))
    fixed_references = []
    for item in references:
        if type(item) is not dict or set(item) != {
                "scope", "reference_solution_id", "reference_version_id"}:
            raise ApplicationError("VALIDATION_FAILED")
        if item["scope"] not in ("PROJECT", "GLOBAL"):
            raise ApplicationError("VALIDATION_FAILED")
        fixed_references.append(OutlineReferenceRef(
            item["scope"], _uuid(item["reference_solution_id"]),
            _uuid(item["reference_version_id"])))
    return OutlineVersionDraftInput(
        project, outline, tuple(_uuid(item) for item in sections),
        tuple(fixed_requirements), tuple(fixed_references),
        tuple(missing), tuple(conflicts))


def _failure(error: OutlineVersionCreateError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "SOURCE_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(view: OutlineVersionInitialView, project: uuid.UUID,
              outline: uuid.UUID) -> dict[str, object]:
    if (type(view) is not OutlineVersionInitialView
            or view.project_id != project or view.solution_outline_id != outline
            or type(view.created_at) is not datetime
            or view.created_at.tzinfo is None or view.created_at.utcoffset() is None
            or view.version_state != "DRAFT"
            or view.review_ref is not None or view.review_round_ref is not None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "solution_outline_version_id": str(view.solution_outline_version_id),
        "solution_outline_id": str(outline), "project_id": str(project),
        "version_no": view.version_no, "version_state": "DRAFT",
        "content_fingerprint": view.content_fingerprint.hex(),
        "missing_declarations": list(view.missing_declarations),
        "conflict_declarations": list(view.conflict_declarations),
        "declared_section_count": view.declared_section_count,
        "declared_requirement_count": view.declared_requirement_count,
        "declared_reference_count": view.declared_reference_count,
        "supersedes_version_ref": (
            str(view.supersedes_version_ref)
            if view.supersedes_version_ref is not None else None),
        "review_ref": None, "review_round_ref": None,
        "created_by": str(view.created_by),
        "created_at": view.created_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
    }


def create_outline_version_create_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    creates: OutlineVersionCreateService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, creates)):
        raise ValueError("OutlineVersion HTTP dependencies are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/solution-outlines/{outline_id}/versions")
    async def create(project_id: str, outline_id: str, request: Request) -> JSONResponse:
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
        key, project, outline = (
            _idempotency_header(headers), _uuid(project_id), _uuid(outline_id))
        draft = _draft(await _body(request, headers), project, outline)
        trace = uuid.UUID(request.state.trace_id)
        try:
            view = await run_in_threadpool(creates.create, CreateOutlineVersion(
                token, csrf, trace, draft, key))
        except OutlineVersionCreateError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = _response(view, project, outline)
        location = (
            f"/api/v1/projects/{project}/solution-outlines/{outline}"
            f"/versions/{view.solution_outline_version_id}")
        return JSONResponse(
            {"data": data, "trace_id": str(trace)}, status_code=201,
            headers={"Cache-Control": "no-store", "Location": location},
        )

    return router
