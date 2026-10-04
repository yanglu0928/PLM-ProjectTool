"""Opt-in exact User candidate lookup for a current ProjectManager."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _csrf_header, _session_cookie, _session_failure
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.project.api.create_project import _read_json
from plm_assistant.modules.project.application.member_candidates import (
    MemberCandidateQuery, MemberCandidateView, ProjectMemberCandidateError,
    ProjectMemberCandidateService,
)


def create_project_member_candidate_router(*, sessions: SessionService,
                                           candidates: ProjectMemberCandidateService,
                                           origins: LoginOriginPolicy) -> APIRouter:
    if any(item is None for item in (sessions, candidates, origins)):
        raise ValueError("candidate router dependencies are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/member-candidates:resolve")
    async def exact_candidate(project_id: uuid.UUID, request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf = _session_cookie(headers), _csrf_header(headers)
        try:
            await run_in_threadpool(sessions.validate, token, csrf_token=csrf, require_csrf=True)
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if project_id.int == 0:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        if request.query_params:
            raise ApplicationError("REQUEST_MALFORMED")
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != {"username"}:
            raise ApplicationError("REQUEST_MALFORMED")
        raw = body["username"]
        if type(raw) is not str or not raw or len(raw) > 255:
            raise ApplicationError("VALIDATION_FAILED")
        try:
            result = await run_in_threadpool(
                candidates.exact,
                MemberCandidateQuery(token, csrf, uuid.UUID(request.state.trace_id), project_id, raw),
            )
        except ProjectMemberCandidateError as exc:
            raise ApplicationError({
                "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
                "VALIDATION_FAILED": "VALIDATION_FAILED",
                "AUTH_RATE_LIMITED": "AUTH_RATE_LIMITED",
            }.get(exc.code, "SYSTEM_UNAVAILABLE")) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if result is not None and (type(result) is not MemberCandidateView
                                   or type(result.user_id) is not uuid.UUID
                                   or result.user_id.int == 0
                                   or type(result.display_name) is not str
                                   or not result.display_name):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({
            "data": {"candidate": None if result is None else {
                "user_id": str(result.user_id), "display_name": result.display_name,
            }},
            "trace_id": request.state.trace_id,
        }, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    return router
