"""Opt-in project-only GLOBAL Reference candidate GET projection."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.application.list_global_reference_candidates import (
    GlobalReferenceCandidate,
)
from plm_assistant.modules.solution.application.read_global_reference_candidates import (
    GlobalReferenceCandidateReadError, GlobalReferenceCandidateReadPage,
    GlobalReferenceCandidateReadQuery, GlobalReferenceCandidateReadService,
)

from .reference_read import _uuid


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)


def _failure(error: GlobalReferenceCandidateReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "REQUEST_MALFORMED": "REQUEST_MALFORMED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _public(item: GlobalReferenceCandidate) -> dict[str, object]:
    if (type(item) is not GlobalReferenceCandidate
            or type(item.reference_solution_id) is not uuid.UUID
            or item.reference_solution_id.int == 0
            or type(item.reference_version_id) is not uuid.UUID
            or item.reference_version_id.int == 0
            or type(item.display_label) is not str
            or not 1 <= len(item.display_label) <= 160
            or type(item.version_no) is not int or item.version_no <= 0
            or item.eligibility_state != "ELIGIBLE"):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "reference_solution_id": str(item.reference_solution_id),
        "reference_version_id": str(item.reference_version_id),
        "display_label": item.display_label,
        "version_no": item.version_no,
        "eligibility_state": item.eligibility_state,
    }


def create_project_global_reference_candidate_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: GlobalReferenceCandidateReadService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads)):
        raise ValueError("project GLOBAL candidate HTTP dependencies required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/global-reference-candidates",
                 include_in_schema=False)
    async def write_closed(project_id: str) -> None:
        raise ApplicationError("RESOURCE_NOT_FOUND")

    @router.get("/api/v1/projects/{project_id}/global-reference-candidates")
    async def list_candidates(project_id: str, request: Request) -> JSONResponse:
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
        project = _uuid(project_id)
        entries = list(request.query_params.multi_items())
        if (len(entries) > 2 or len({key for key, _ in entries}) != len(entries)
                or any(key not in {"page_size", "cursor"} for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        params = dict(entries)
        raw_size = params.get("page_size", "20")
        if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 100:
            raise ApplicationError("VALIDATION_FAILED")
        trace = uuid.UUID(request.state.trace_id)
        try:
            page = await run_in_threadpool(
                reads.list, GlobalReferenceCandidateReadQuery(token, trace, project),
                page_size=int(raw_size), cursor=params.get("cursor"))
        except GlobalReferenceCandidateReadError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not GlobalReferenceCandidateReadPage
                or type(page.items) is not tuple
                or len(page.items) > int(raw_size)
                or type(page.has_more) is not bool
                or (page.has_more and (
                    type(page.next_cursor) is not str or not page.next_cursor))
                or (not page.has_more and page.next_cursor is not None)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({
            "data": {"items": [_public(item) for item in page.items],
                     "next_cursor": page.next_cursor, "has_more": page.has_more},
            "trace_id": str(trace),
        }, headers={"Cache-Control": "no-store"})

    return router
