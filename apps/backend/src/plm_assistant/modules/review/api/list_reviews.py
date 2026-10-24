"""Opt-in frozen REVIEW_LIST HTTP boundary; Windows wiring is separate."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError,
    LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.capability.api.commands import _canonical_uuid, _instant
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.review.application.list_contract import (
    MyReviewAssignmentSummary,
    ReviewListActiveRoundSummary,
    ReviewListItem,
    ReviewListPage,
    ReviewListQuery,
)
from plm_assistant.modules.review.application.list_service import (
    ReviewListError,
    ReviewListService,
)

from .list_cursor import ReviewListCursorCodec


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)


def _failure(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "REQUEST_MALFORMED": "REQUEST_MALFORMED",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def _assignment(value: MyReviewAssignmentSummary) -> dict[str, object]:
    if type(value) is not MyReviewAssignmentSummary:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    value.__post_init__()
    return {
        "assignment_id": str(value.assignment_id),
        "state": value.state,
        "decision": value.decision,
        "decided_at": (
            None if value.decided_at is None else _instant(value.decided_at)
        ),
    }


def _active_round(value: ReviewListActiveRoundSummary) -> dict[str, object]:
    if type(value) is not ReviewListActiveRoundSummary:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    value.__post_init__()
    return {
        "review_round_id": str(value.review_round_id),
        "round_no": value.round_no,
        "subject_version_ref": str(value.subject_version_id),
        "started_at": _instant(value.started_at),
        "my_assignment": (
            None if value.my_assignment is None
            else _assignment(value.my_assignment)
        ),
    }


def _public(value: ReviewListItem) -> dict[str, object]:
    if type(value) is not ReviewListItem:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    value.__post_init__()
    return {
        "review_id": str(value.review_id),
        "project_id": str(value.project_id),
        "subject_ref": {
            "resource_type": value.subject_type,
            "resource_id": str(value.subject_id),
        },
        "policy_code": value.policy_code,
        "state": value.state,
        "created_by": str(value.created_by),
        "created_at": _instant(value.created_at),
        "etag": value.etag,
        "active_round": (
            None if value.active_round is None
            else _active_round(value.active_round)
        ),
    }


def create_review_list_router(
    *,
    origins: LoginOriginPolicy,
    lists: ReviewListService,
    cursors: ReviewListCursorCodec,
) -> APIRouter:
    """Create an explicitly injected list router; default app stays closed."""
    if any(value is None for value in (origins, lists, cursors)):
        raise ValueError("Review list HTTP dependencies are required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/reviews")
    async def list_reviews(project_id: str, request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        project = _canonical_uuid(project_id)
        token = _session_cookie(headers)
        trace_id = uuid.UUID(request.state.trace_id)
        entries = list(request.query_params.multi_items())
        if (len(entries) > 3
                or len({key for key, _ in entries}) != len(entries)
                or any(key not in {"page_size", "cursor", "view"}
                       for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        params = dict(entries)
        raw_size = params.get("page_size", "50")
        view = params.get("view", "all")
        if (_PAGE_SIZE.fullmatch(raw_size) is None
                or not 1 <= int(raw_size) <= 200
                or view not in {"all", "my_pending"}):
            raise ApplicationError("VALIDATION_FAILED")
        page_size = int(raw_size)
        try:
            before = None
            if "cursor" in params:
                before = cursors.decode(
                    params["cursor"],
                    session_token=token,
                    project_id=project,
                    view=view,
                    page_size=page_size,
                )
            query = ReviewListQuery(
                token, trace_id, project, view, before, page_size,
            )
            page = await run_in_threadpool(lists.list, query)
            if type(page) is not ReviewListPage:
                raise ValueError()
            page.__post_init__()
            if (len(page.items) > page_size
                    or any(item.project_id != project for item in page.items)):
                raise ValueError()
            next_cursor = (
                cursors.encode(
                    session_token=token,
                    project_id=project,
                    view=view,
                    page_size=page_size,
                    position=page.next_position,
                )
                if page.has_more and page.next_position is not None else None
            )
            data = {
                "items": [_public(item) for item in page.items],
                "next_cursor": next_cursor,
                "has_more": page.has_more,
            }
        except ApplicationError:
            raise
        except ReviewListError as error:
            raise _failure(error.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": data, "trace_id": str(trace_id)},
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
