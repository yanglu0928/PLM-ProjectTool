"""Opt-in frozen SOL_SECTION_LIST HTTP boundary."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.api.reference_read import _timestamp, _uuid
from plm_assistant.modules.solution.api.section_list_cursor import SectionListCursorCodec
from plm_assistant.modules.solution.api.section_read import _failure
from plm_assistant.modules.solution.application.read_section import (
    SectionListPage, SectionReadError, SectionReadQuery, SectionReadService,
    SectionSummaryView,
)


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)


def _public(item: SectionSummaryView, project: uuid.UUID) -> dict[str, object]:
    if (type(item) is not SectionSummaryView
            or item.project_id != project
            or type(item.solution_section_id) is not uuid.UUID
            or item.solution_section_id.int == 0
            or type(item.solution_outline_id) is not uuid.UUID
            or item.solution_outline_id.int == 0
            or type(item.section_key) is not str or not item.section_key
            or item.section_state not in ("ACTIVE", "ARCHIVED")
            or (item.current_approved_version_ref is not None
                and (type(item.current_approved_version_ref) is not uuid.UUID
                     or item.current_approved_version_ref.int == 0))
            or type(item.etag) is not str
            or re.fullmatch(r'"v(0|[1-9][0-9]*)"', item.etag,
                            flags=re.ASCII) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "solution_section_id": str(item.solution_section_id),
        "solution_outline_id": str(item.solution_outline_id),
        "project_id": str(project), "section_key": item.section_key,
        "section_state": item.section_state,
        "current_approved_version_ref": (
            str(item.current_approved_version_ref)
            if item.current_approved_version_ref is not None else None),
        "created_at": _timestamp(item.created_at), "etag": item.etag,
    }


def create_section_list_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: SectionReadService, cursors: SectionListCursorCodec,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads, cursors)):
        raise ValueError("SolutionSection List HTTP dependencies required")
    router = APIRouter()

    # Keep POST hidden in read-only composition; write mode mounts CREATE first.
    @router.post("/api/v1/projects/{project_id}/solution-sections",
                 include_in_schema=False)
    async def create_closed(project_id: str) -> None:
        raise ApplicationError("RESOURCE_NOT_FOUND")

    @router.get("/api/v1/projects/{project_id}/solution-sections")
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
                reads.list_current, SectionReadQuery(token, trace, project),
                after_section_id=after, limit=size)
        except SectionReadError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not SectionListPage or type(page.items) is not tuple
                or len(page.items) > size or type(page.has_more) is not bool
                or (page.has_more and (not page.items
                    or page.next_after_section_id
                    != page.items[-1].solution_section_id))
                or (not page.has_more and page.next_after_section_id is not None)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = [_public(item, project) for item in page.items]
        try:
            next_cursor = (cursors.encode(
                session_token=token, project_id=project, page_size=size,
                section_id=page.next_after_section_id)
                if page.has_more else None)
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({
            "data": {"items": data, "next_cursor": next_cursor,
                     "has_more": page.has_more},
            "trace_id": str(trace),
        }, headers={"Cache-Control": "no-store"})

    return router
