"""Opt-in frozen PLAN_LIST HTTP boundary."""

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
from plm_assistant.modules.plan.application.read_plan import (
    PlanListPage, PlanReadError, PlanReadQuery, PlanReadService, PlanSummaryView,
)
from ._request import canonical_uuid
from .list_cursor import PlanListCursorCodec
from .read_plan import _failure


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)


def _public(item: PlanSummaryView, project: uuid.UUID) -> dict[str, object]:
    if (type(item) is not PlanSummaryView or type(item.plan_id) is not uuid.UUID
            or item.plan_id.int == 0 or item.project_id != project
            or type(item.name) is not str or not item.name
            or item.plan_state not in ("ACTIVE", "ARCHIVED")
            or item.current_approved_version_ref is not None
            or type(item.created_at) is not datetime
            or item.created_at.tzinfo is None or item.created_at.utcoffset() is None
            or type(item.etag) is not str
            or re.fullmatch(r'"v(0|[1-9][0-9]*)"', item.etag,
                            flags=re.ASCII) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "plan_id": str(item.plan_id), "project_id": str(project), "name": item.name,
        "plan_state": item.plan_state, "current_approved_version_ref": None,
        "created_at": item.created_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"), "etag": item.etag,
    }


def create_plan_list_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: PlanReadService, cursors: PlanListCursorCodec,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads, cursors)):
        raise ValueError("Plan List HTTP dependencies required")
    router = APIRouter()

    # Keep POST closed when only the read router is mounted; CREATE is mounted first.
    @router.post("/api/v1/projects/{project_id}/plans", include_in_schema=False)
    async def create_closed(project_id: str) -> None:
        raise ApplicationError("RESOURCE_NOT_FOUND")

    @router.get("/api/v1/projects/{project_id}/plans")
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
        project = canonical_uuid(project_id)
        entries = list(request.query_params.multi_items())
        if (len(entries) > 2 or len({key for key, _ in entries}) != len(entries)
                or any(key not in {"page_size", "cursor"} for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        params = dict(entries)
        raw_size = params.get("page_size", "50")
        if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 200:
            raise ApplicationError("VALIDATION_FAILED")
        size = int(raw_size)
        after = (cursors.decode(params["cursor"], session_token=token,
                                project_id=project, page_size=size)
                 if "cursor" in params else None)
        trace = uuid.UUID(request.state.trace_id)
        try:
            page = await run_in_threadpool(
                reads.list_current, PlanReadQuery(token, trace, project),
                after_created_at=after[0] if after else None,
                after_plan_id=after[1] if after else None, limit=size)
        except PlanReadError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not PlanListPage or type(page.items) is not tuple
                or len(page.items) > size or type(page.has_more) is not bool
                or (page.has_more and (not page.items
                    or page.next_after_created_at != page.items[-1].created_at
                    or page.next_after_plan_id != page.items[-1].plan_id))
                or (not page.has_more and (
                    page.next_after_created_at is not None
                    or page.next_after_plan_id is not None))):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = [_public(item, project) for item in page.items]
        try:
            next_cursor = (cursors.encode(
                session_token=token, project_id=project, page_size=size,
                created_at=page.next_after_created_at,
                plan_id=page.next_after_plan_id) if page.has_more else None)
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({
            "data": {"items": data, "next_cursor": next_cursor,
                     "has_more": page.has_more},
            "trace_id": str(trace),
        }, headers={"Cache-Control": "no-store"})

    return router
