"""Opt-in OUTPUT_REQUEST_LIST endpoint with a scoped opaque cursor."""
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
from plm_assistant.modules.output.api.list_cursor import OutputRequestListCursorCodec
from plm_assistant.modules.output.api.read_request import (
    _error as _single_error, output_request_view_data,
)
from plm_assistant.modules.output.application.list_requests import (
    OutputRequestListError, OutputRequestListQuery, OutputRequestListService,
)
from plm_assistant.modules.platform.application.errors import ApplicationError

_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)


def create_output_request_list_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    service: OutputRequestListService, cursors: OutputRequestListCursorCodec,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, service, cursors)):
        raise ValueError("OutputRequest list HTTP dependencies are required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/output-requests")
    async def list_output_requests(project_id: uuid.UUID,
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
        if not project_id.int:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        entries = list(request.query_params.multi_items())
        if (len(entries) > 2 or len({key for key, _ in entries}) != len(entries)
                or any(key not in {"page_size", "cursor"} for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        params = dict(entries)
        raw_size = params.get("page_size", "50")
        if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 200:
            raise ApplicationError("VALIDATION_FAILED")
        page_size = int(raw_size)
        after_at = after_id = None
        if "cursor" in params:
            after_at, after_id = cursors.decode(
                params["cursor"], session_token=token,
                project_id=project_id, page_size=page_size,
            )
        try:
            trace_id = uuid.UUID(request.state.trace_id)
        except (AttributeError, TypeError, ValueError):
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        query = OutputRequestListQuery(
            token, trace_id, project_id, page_size,
            after_requested_at=after_at, after_request_id=after_id,
        )
        try:
            page = await run_in_threadpool(service.list_page, query)
        except OutputRequestListError as exc:
            raise _single_error(
                __import__(
                    "plm_assistant.modules.output.application.read_request",
                    fromlist=["OutputRequestReadError"],
                ).OutputRequestReadError(exc.code),
            ) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page.items) is not tuple or type(page.has_more) is not bool
                or (page.has_more and (
                    page.next_requested_at is None or page.next_request_id is None))
                or ((page.next_requested_at is None) != (page.next_request_id is None))):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = None
        if page.has_more:
            next_cursor = cursors.encode(
                session_token=token, project_id=project_id, page_size=page_size,
                requested_at=page.next_requested_at,
                request_id=page.next_request_id,
            )
        return JSONResponse(
            {"data": {
                "items": [output_request_view_data(item) for item in page.items],
                "next_cursor": next_cursor,
                "has_more": page.has_more,
            }, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store"},
        )

    return router
