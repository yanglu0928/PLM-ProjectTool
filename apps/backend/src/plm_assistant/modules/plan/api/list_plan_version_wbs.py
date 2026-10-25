"""Opt-in keyset-paged PLAN_VERSION_WBS_LIST HTTP boundary."""

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
from plm_assistant.modules.auth.application.session_service import (
    SessionError, SessionService,
)
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.plan.api.wbs_list_cursor import PlanVersionWbsCursorCodec
from plm_assistant.modules.plan.application.list_plan_version_wbs import (
    PlanVersionWbsPage, PlanVersionWbsReadError, PlanVersionWbsReadQuery,
    PlanVersionWbsReadService, PlanVersionWbsItemView,
)
from ._request import canonical_uuid


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_ITEM_FIELDS = {
    "wbs_item_id", "parent_item_id", "wbs_code", "name", "level", "category",
    "owner_ref", "support_role_refs", "planned_start", "planned_finish",
    "duration_minutes", "actual_start", "actual_finish", "item_state",
    "entry_conditions", "acceptance_criteria", "requirement_refs", "solution_refs",
    "prototype_refs", "evidence_refs", "output_refs", "risk",
    "explicit_exclusion", "milestone_refs",
}


def _failure(error: PlanVersionWbsReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _public(item: PlanVersionWbsItemView, *, project: uuid.UUID) -> dict[str, object]:
    if (type(item) is not PlanVersionWbsItemView
            or type(item.wbs_item_id) is not uuid.UUID or item.wbs_item_id.int == 0
            or type(item.ordinal) is not int or item.ordinal < 1
            or type(item.data) is not dict or set(item.data) != _ITEM_FIELDS
            or item.data.get("wbs_item_id") != str(item.wbs_item_id)
            or type(item.data.get("parent_item_id")) not in (str, type(None))
            or type(item.data.get("solution_refs")) is not list
            or type(item.data.get("requirement_refs")) is not list
            or type(item.data.get("evidence_refs")) is not list
            or type(item.data.get("prototype_refs")) is not list
            or type(item.data.get("milestone_refs")) is not list):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return dict(item.data)


def create_plan_version_wbs_list_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: PlanVersionWbsReadService, cursors: PlanVersionWbsCursorCodec,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads, cursors)):
        raise ValueError("PlanVersion WBS list dependencies are required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/plans/{plan_id}/versions/"
                "{plan_version_id}/wbs-items")
    async def list_items(project_id: str, plan_id: str, plan_version_id: str,
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
        project, plan, version = (canonical_uuid(value) for value in (
            project_id, plan_id, plan_version_id))
        entries = list(request.query_params.multi_items())
        if (len(entries) > 2 or len({key for key, _ in entries}) != len(entries)
                or any(key not in {"page_size", "cursor"} for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        params = dict(entries)
        raw_size = params.get("page_size", "50")
        if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 200:
            raise ApplicationError("VALIDATION_FAILED")
        page_size = int(raw_size)
        after = (cursors.decode(
            params["cursor"], session_token=token, project_id=project,
            plan_id=plan, plan_version_id=version, page_size=page_size,
        ) if "cursor" in params else None)
        trace = uuid.UUID(request.state.trace_id)
        try:
            page = await run_in_threadpool(
                reads.list_current,
                PlanVersionWbsReadQuery(token, trace, project),
                plan_id=plan, plan_version_id=version,
                after_ordinal=after[0] if after else None,
                after_wbs_item_id=after[1] if after else None,
                limit=page_size,
            )
        except PlanVersionWbsReadError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not PlanVersionWbsPage or page.plan_id != plan
                or page.plan_version_id != version or page.project_id != project
                or type(page.items) is not tuple or len(page.items) > page_size
                or type(page.has_more) is not bool
                or (page.has_more and (not page.items
                    or page.next_ordinal != page.items[-1].ordinal
                    or page.next_wbs_item_id != page.items[-1].wbs_item_id))
                or (not page.has_more and (page.next_ordinal is not None
                    or page.next_wbs_item_id is not None))):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = [_public(item, project=project) for item in page.items]
        try:
            next_cursor = (cursors.encode(
                session_token=token, project_id=project, plan_id=plan,
                plan_version_id=version, page_size=page_size,
                ordinal=page.next_ordinal, wbs_item_id=page.next_wbs_item_id,
            ) if page.has_more else None)
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({
            "data": {"items": data, "next_cursor": next_cursor,
                     "has_more": page.has_more},
            "trace_id": str(trace),
        }, headers={"Cache-Control": "no-store"})

    return router
