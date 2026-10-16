"""Opt-in frozen SOL_SPEC_LIST version-summary HTTP boundary."""

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
from plm_assistant.modules.solution.api.structured_spec_list_cursor import StructuredSpecListCursorCodec
from plm_assistant.modules.solution.api.structured_spec_read import _failure
from plm_assistant.modules.solution.application.read_structured_spec import (
    StructuredSpecListPage, StructuredSpecReadError, StructuredSpecReadQuery,
    StructuredSpecReadService, StructuredSpecSummaryView,
)


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_TYPES = ("PROCESS_MODEL", "INTERFACE_SPEC", "MIGRATION_SPEC", "PERMISSION_DESIGN")
_STATES = ("DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED")


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _public(item: StructuredSpecSummaryView, project: uuid.UUID) -> dict[str, object]:
    if (type(item) is not StructuredSpecSummaryView
            or item.project_id != project
            or not _id(item.structured_solution_spec_id)
            or not _id(item.spec_series_id)
            or item.spec_type not in _TYPES
            or type(item.version_no) is not int or item.version_no < 1
            or item.version_state not in _STATES
            or any(type(digest) is not bytes or len(digest) != 32
                   for digest in (item.content_fingerprint,
                                  item.payload_fingerprint))
            or (item.supersedes_version_ref is None) != (item.version_no == 1)
            or (item.review_ref is None) != (item.review_round_ref is None)
            or not _id(item.created_by)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "structured_solution_spec_id": str(item.structured_solution_spec_id),
        "spec_series_id": str(item.spec_series_id),
        "project_id": str(project), "spec_type": item.spec_type,
        "version_no": item.version_no, "version_state": item.version_state,
        "content_fingerprint": item.content_fingerprint.hex(),
        "payload_fingerprint": item.payload_fingerprint.hex(),
        "supersedes_version_ref": (
            str(item.supersedes_version_ref)
            if item.supersedes_version_ref is not None else None),
        "review_ref": str(item.review_ref) if item.review_ref is not None else None,
        "review_round_ref": (
            str(item.review_round_ref)
            if item.review_round_ref is not None else None),
        "created_by": str(item.created_by),
        "created_at": _timestamp(item.created_at),
    }


def create_structured_spec_list_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: StructuredSpecReadService, cursors: StructuredSpecListCursorCodec,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads, cursors)):
        raise ValueError("StructuredSpec List HTTP dependencies required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/structured-solution-specs",
                 include_in_schema=False)
    async def create_closed(project_id: str) -> None:
        raise ApplicationError("RESOURCE_NOT_FOUND")

    @router.get("/api/v1/projects/{project_id}/structured-solution-specs")
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
        before = (cursors.decode(
            params["cursor"], session_token=token,
            project_id=project, page_size=size)
            if "cursor" in params else None)
        trace = uuid.UUID(request.state.trace_id)
        try:
            page = await run_in_threadpool(
                reads.list_versions,
                StructuredSpecReadQuery(token, trace, project),
                before_spec_id=before, limit=size)
        except StructuredSpecReadError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not StructuredSpecListPage
                or type(page.items) is not tuple or len(page.items) > size
                or type(page.has_more) is not bool
                or (page.has_more and (not page.items
                    or page.next_before_spec_id
                    != page.items[-1].structured_solution_spec_id))
                or (not page.has_more and page.next_before_spec_id is not None)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = [_public(item, project) for item in page.items]
        try:
            next_cursor = (cursors.encode(
                session_token=token, project_id=project, page_size=size,
                before_spec_id=page.next_before_spec_id)
                if page.has_more else None)
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({
            "data": {"items": data, "next_cursor": next_cursor,
                     "has_more": page.has_more},
            "trace_id": str(trace),
        }, headers={"Cache-Control": "no-store"})

    return router
