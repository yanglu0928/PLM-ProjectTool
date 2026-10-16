"""Opt-in frozen SOL_SECTION_GET HTTP boundary."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.api.reference_read import _uuid
from plm_assistant.modules.solution.application.read_section import (
    SectionCurrentView, SectionReadError, SectionReadQuery, SectionReadService,
)


def _response(view: SectionCurrentView, project: uuid.UUID,
              identity: uuid.UUID) -> dict[str, object]:
    if (type(view) is not SectionCurrentView
            or view.project_id != project or view.solution_section_id != identity
            or type(view.solution_outline_id) is not uuid.UUID
            or view.solution_outline_id.int == 0
            or type(view.section_key) is not str or not view.section_key
            or view.section_state not in ("ACTIVE", "ARCHIVED")
            or (view.current_approved_version_ref is not None
                and (type(view.current_approved_version_ref) is not uuid.UUID
                     or view.current_approved_version_ref.int == 0))
            or type(view.created_by) is not uuid.UUID or view.created_by.int == 0
            or type(view.created_at) is not datetime
            or view.created_at.tzinfo is None or view.created_at.utcoffset() is None
            or type(view.etag) is not str
            or re.fullmatch(r'"v(0|[1-9][0-9]*)"', view.etag,
                            flags=re.ASCII) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "solution_section_id": str(identity),
        "solution_outline_id": str(view.solution_outline_id),
        "project_id": str(project), "section_key": view.section_key,
        "section_state": view.section_state,
        "current_approved_version_ref": (
            str(view.current_approved_version_ref)
            if view.current_approved_version_ref is not None else None),
        "created_by": str(view.created_by),
        "created_at": view.created_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
        "etag": view.etag,
    }


def _failure(error: SectionReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def create_section_read_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: SectionReadService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads)):
        raise ValueError("SolutionSection read dependencies are required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/solution-sections/{section_id}")
    async def get(project_id: str, section_id: str,
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
        project, identity = _uuid(project_id), _uuid(section_id)
        trace = uuid.UUID(request.state.trace_id)
        try:
            view = await run_in_threadpool(
                reads.get_current, SectionReadQuery(token, trace, project), identity)
        except SectionReadError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = _response(view, project, identity)
        return JSONResponse(
            {"data": data, "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": view.etag})

    return router
