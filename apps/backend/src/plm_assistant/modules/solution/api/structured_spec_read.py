"""Opt-in frozen SOL_SPEC_GET fixed-history HTTP boundary."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.application.read_structured_spec import (
    StructuredSpecHistoryView, StructuredSpecReadError,
    StructuredSpecReadQuery, StructuredSpecReadService,
)
from .reference_read import _timestamp, _uuid


def _failure(error: StructuredSpecReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _detail(view: StructuredSpecHistoryView, project: uuid.UUID,
            spec: uuid.UUID) -> dict[str, object]:
    if (type(view) is not StructuredSpecHistoryView
            or view.structured_solution_spec_id != spec
            or view.project_id != project
            or view.version_state not in (
                "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED",
                "SUPERSEDED", "RESTRICTED")
            or view.artifact_ids):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    try:
        payload = view.payload()
        if type(payload) is not dict:
            raise ValueError("invalid payload")
        return {
            "structured_solution_spec_id": str(spec),
            "spec_series_id": str(view.spec_series_id),
            "project_id": str(project), "spec_type": view.spec_type,
            "version_no": view.version_no, "version_state": view.version_state,
            "content_fingerprint": view.content_fingerprint.hex(),
            "payload": payload,
            "payload_fingerprint": view.payload_fingerprint.hex(),
            "requirement_refs": [{
                "requirement_id": str(item.requirement_id),
                "requirement_version_id": str(item.requirement_version_id),
            } for item in view.requirement_refs],
            "section_refs": [{
                "solution_section_id": str(item.solution_section_id),
                "solution_section_version_id": str(item.solution_section_version_id),
            } for item in view.section_refs],
            "evidence_ids": [str(item) for item in view.evidence_ids],
            "artifact_ids": [],
            "declared_requirement_count": len(view.requirement_refs),
            "declared_section_count": len(view.section_refs),
            "declared_evidence_count": len(view.evidence_ids),
            "supersedes_version_ref": (
                str(view.supersedes_version_ref)
                if view.supersedes_version_ref is not None else None),
            "review_ref": str(view.review_ref) if view.review_ref else None,
            "review_round_ref": (
                str(view.review_round_ref) if view.review_round_ref else None),
            "created_by": str(view.created_by),
            "created_at": _timestamp(view.created_at),
        }
    except Exception:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None


def create_structured_spec_read_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: StructuredSpecReadService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads)):
        raise ValueError("StructuredSpec read HTTP dependencies required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/structured-solution-specs/{spec_id}")
    async def get_spec(project_id: str, spec_id: str,
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
        project, spec = _uuid(project_id), _uuid(spec_id)
        trace = uuid.UUID(request.state.trace_id)
        try:
            view = await run_in_threadpool(
                reads.get, StructuredSpecReadQuery(token, trace, project), spec)
        except StructuredSpecReadError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({
            "data": _detail(view, project, spec),
            "trace_id": str(trace),
        }, headers={"Cache-Control": "no-store"})

    return router
