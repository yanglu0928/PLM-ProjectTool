"""Opt-in frozen PLAN_VERSION_LIST HTTP boundary."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import (
    SessionError, SessionService,
)
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.plan.api.version_list_cursor import PlanVersionListCursorCodec
from plm_assistant.modules.plan.application.list_plan_versions import (
    PlanVersionListError, PlanVersionListPage, PlanVersionListQuery,
    PlanVersionListService, PlanVersionSummary,
)
from plm_assistant.modules.plan.api._request import canonical_uuid


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)


def _public(item: PlanVersionSummary, *, project_id: uuid.UUID,
            plan_id: uuid.UUID) -> dict[str, object]:
    if (type(item) is not PlanVersionSummary
            or item.plan_id != plan_id or item.project_id != project_id
            or type(item.plan_version_id) is not uuid.UUID or item.plan_version_id.int == 0
            or type(item.version_no) is not int or item.version_no < 1
            or item.version_state not in (
                "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED")
            or type(item.created_by) is not uuid.UUID or item.created_by.int == 0
            or type(item.created_at) is not datetime
            or item.created_at.tzinfo is None or item.created_at.utcoffset() is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "plan_version_id": str(item.plan_version_id), "plan_id": str(plan_id),
        "project_id": str(project_id), "version_no": item.version_no,
        "version_state": item.version_state,
        "supersedes_version_ref": str(item.supersedes_version_ref)
            if item.supersedes_version_ref else None,
        "review_ref": str(item.review_ref) if item.review_ref else None,
        "review_round_ref": str(item.review_round_ref) if item.review_round_ref else None,
        "created_by": str(item.created_by),
        "created_at": item.created_at.isoformat().replace("+00:00", "Z"),
    }


def create_plan_version_list_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: PlanVersionListService, cursors: PlanVersionListCursorCodec,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads, cursors)):
        raise ValueError("PlanVersion list dependencies are required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/plans/{plan_id}/versions")
    async def list_versions(project_id: str, plan_id: str,
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
        project, plan = canonical_uuid(project_id), canonical_uuid(plan_id)
        entries = list(request.query_params.multi_items())
        if (len(entries) > 2 or len({key for key, _ in entries}) != len(entries)
                or any(key not in {"page_size", "cursor"} for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        params = dict(entries)
        raw_size = params.get("page_size", "50")
        if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 200:
            raise ApplicationError("VALIDATION_FAILED")
        page_size = int(raw_size)
        after = cursors.decode(
            params["cursor"], session_token=token, project_id=project,
            plan_id=plan, page_size=page_size) if "cursor" in params else None
        trace = uuid.UUID(request.state.trace_id)
        try:
            page = await run_in_threadpool(
                reads.list_current, PlanVersionListQuery(token, trace, project),
                plan_id=plan, after_version_no=after, limit=page_size)
        except PlanVersionListError as error:
            code = {
                "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
                "VALIDATION_FAILED": "VALIDATION_FAILED",
            }.get(error.code, "SYSTEM_UNAVAILABLE")
            raise ApplicationError(code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not PlanVersionListPage or type(page.items) is not tuple
                or len(page.items) > page_size or type(page.has_more) is not bool
                or (page.has_more and (not page.items
                    or page.next_version_no != page.items[-1].version_no))
                or (not page.has_more and page.next_version_no is not None)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = [_public(item, project_id=project, plan_id=plan) for item in page.items]
        try:
            next_cursor = cursors.encode(
                session_token=token, project_id=project, plan_id=plan,
                page_size=page_size, version_no=page.next_version_no
            ) if page.has_more else None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({
            "data": {"items": data, "next_cursor": next_cursor,
                     "has_more": page.has_more},
            "trace_id": str(trace),
        }, headers={"Cache-Control": "no-store"})

    return router
