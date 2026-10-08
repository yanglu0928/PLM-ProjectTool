"""Opt-in PROJECT ReferenceSolution List HTTP projection."""

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
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec
from plm_assistant.modules.solution.api.reference_read import _failure, _timestamp, _uuid
from plm_assistant.modules.solution.application.read_reference import (
    ReferenceListPage, ReferenceReadError, ReferenceReadQuery,
    ReferenceReadService, ReferenceSummaryView,
)


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)


def _public(item: ReferenceSummaryView, project: uuid.UUID) -> dict[str, object]:
    if (type(item) is not ReferenceSummaryView
            or item.scope != "PROJECT" or item.project_id != project):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "reference_solution_id": str(item.reference_solution_id),
        "reference_version_id": str(item.reference_version_id),
        "scope": "PROJECT", "project_id": str(project),
        "name": item.name, "eligibility_state": item.eligibility_state,
        "version_no": item.version_no, "version_state": item.version_state,
        "created_at": _timestamp(item.created_at), "etag": item.etag,
    }


def create_project_reference_list_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: ReferenceReadService, cursors: ReferenceListCursorCodec,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads, cursors)):
        raise ValueError("PROJECT Reference List HTTP dependencies required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/reference-solutions")
    async def list_project(project_id: str, request: Request) -> JSONResponse:
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
        raw_size = params.get("page_size", "50")
        if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 100:
            raise ApplicationError("VALIDATION_FAILED")
        size = int(raw_size)
        after = (cursors.decode(params["cursor"], session_token=token,
                                project_id=project, page_size=size)
                 if "cursor" in params else None)
        trace = uuid.UUID(request.state.trace_id)
        try:
            page = await run_in_threadpool(
                reads.list_current, ReferenceReadQuery(token, trace, project),
                after_reference_solution_id=after, limit=size)
        except ReferenceReadError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not ReferenceListPage or type(page.items) is not tuple
                or len(page.items) > size or type(page.has_more) is not bool
                or (page.has_more and (not page.items
                    or page.next_after_reference_solution_id
                    != page.items[-1].reference_solution_id))
                or (not page.has_more
                    and page.next_after_reference_solution_id is not None)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = [_public(item, project) for item in page.items]
        try:
            next_cursor = (cursors.encode(
                session_token=token, project_id=project, page_size=size,
                reference_solution_id=page.next_after_reference_solution_id)
                if page.has_more else None)
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({
            "data": {"items": data, "next_cursor": next_cursor,
                     "has_more": page.has_more},
            "trace_id": str(trace),
        }, headers={"Cache-Control": "no-store"})

    return router
