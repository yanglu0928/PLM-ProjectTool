"""Opt-in PROJECT/GLOBAL Reference revision HTTP contract."""

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
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.application.reference_source_qualification import ReferenceSourceRequest
from plm_assistant.modules.solution.application.revise_reference_solution import (
    ReferenceReviseError, ReferenceReviseService, ReferenceRevisionView,
    ReviseReferenceSolution,
)

from .reference_create import _ids, _read_body, _uuid


_FIELDS = frozenset({
    "document_version_ids", "evidence_ids", "source_project_class",
    "deidentification_class", "applicability",
})


def _failure(error: ReferenceReviseError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "VERSION_CONFLICT": "CONFLICT_VERSION",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "SOURCE_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(view: ReferenceRevisionView, *, identity: uuid.UUID,
              scope: str, project_id: uuid.UUID | None) -> tuple[dict[str, object], str]:
    if (type(view) is not ReferenceRevisionView
            or view.reference_solution_id != identity
            or view.scope != scope or view.project_id != project_id
            or type(view.reference_version_id) is not uuid.UUID
            or view.reference_version_id.int == 0
            or type(view.supersedes_version_ref) is not uuid.UUID
            or view.supersedes_version_ref.int == 0
            or type(view.version_no) is not int or view.version_no < 2
            or type(view.content_fingerprint) is not bytes
            or len(view.content_fingerprint) != 32
            or type(view.source_fingerprint) is not bytes
            or len(view.source_fingerprint) != 32
            or type(view.created_at) is not datetime
            or view.created_at.tzinfo is None or view.created_at.utcoffset() is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    etag = f'"v{view.version_no-1}"'
    return ({
        "reference_solution_id": str(view.reference_solution_id),
        "reference_version_id": str(view.reference_version_id),
        "scope": scope,
        "project_id": str(project_id) if project_id is not None else None,
        "version_no": view.version_no,
        "version_state": "DRAFT",
        "supersedes_version_ref": str(view.supersedes_version_ref),
        "created_at": view.created_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
        "etag": etag,
    }, etag)


def _router(*, scope: str, sessions: SessionService, origins: LoginOriginPolicy,
            revises: ReferenceReviseService) -> APIRouter:
    if scope not in ("PROJECT", "GLOBAL") or any(
            value is None for value in (sessions, origins, revises)):
        raise ValueError("Reference revise HTTP dependencies required")
    router = APIRouter()

    async def revise(request: Request, identity_raw: str,
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
        if (type(body["source_project_class"]) is not str
                or type(body["deidentification_class"]) is not str
                or type(body["applicability"]) is not dict):
            raise ApplicationError("VALIDATION_FAILED")
        trace = uuid.UUID(request.state.trace_id)
        sources = ReferenceSourceRequest(
            token, trace, scope, project,
            _ids(body["document_version_ids"]), _ids(body["evidence_ids"]),
            body["source_project_class"], body["deidentification_class"],
            body["applicability"],
        )
        try:
            view = await run_in_threadpool(revises.revise, ReviseReferenceSolution(
                sources, csrf, identity, expected, key))
        except ReferenceReviseError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data, etag = _response(view, identity=identity, scope=scope,
                               project_id=project)
        return JSONResponse(
            {"data": data, "trace_id": str(trace)}, status_code=201,
            headers={"Cache-Control": "no-store", "ETag": etag})

    if scope == "PROJECT":
        @router.post("/api/v1/projects/{project_id}/reference-solutions/"
                     "{reference_solution_id}:revise")
        async def project_revise(project_id: str, reference_solution_id: str,
                                 request: Request) -> JSONResponse:
            return await revise(request, reference_solution_id, project_id)
    else:
        @router.post("/api/v1/global/reference-solutions/{reference_solution_id}:revise")
        async def global_revise(reference_solution_id: str,
                                request: Request) -> JSONResponse:
            return await revise(request, reference_solution_id)
    return router


def create_project_reference_revise_router(*, sessions: SessionService,
                                          origins: LoginOriginPolicy,
                                          revises: ReferenceReviseService) -> APIRouter:
    return _router(scope="PROJECT", sessions=sessions, origins=origins, revises=revises)


def create_global_reference_revise_router(*, sessions: SessionService,
                                         origins: LoginOriginPolicy,
                                         revises: ReferenceReviseService) -> APIRouter:
    return _router(scope="GLOBAL", sessions=sessions, origins=origins, revises=revises)
