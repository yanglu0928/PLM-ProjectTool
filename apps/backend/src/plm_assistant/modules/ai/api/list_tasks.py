"""Opt-in frozen AI_TASK_LIST with current authorization and stable cursor."""

from __future__ import annotations

import re
import uuid
from dataclasses import replace
from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.api.read_task import _public
from plm_assistant.modules.ai.api.task_list_cursor import AITaskListCursorCodec
from plm_assistant.modules.ai.application.task_read import (
    AITaskPage,
    AITaskReadError,
    ListAITasks,
)
from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError,
    LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.platform.application.errors import ApplicationError


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)


class AITaskListPort(Protocol):
    def list(self, query: ListAITasks) -> AITaskPage: ...


def create_ai_task_list_router(*, reads: AITaskListPort,
                               origins: LoginOriginPolicy,
                               cursors: AITaskListCursorCodec) -> APIRouter:
    if any(value is None for value in (reads, origins, cursors)):
        raise ValueError("AI Task list dependencies required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/ai-tasks")
    async def list_tasks(project_id: uuid.UUID, request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        if not project_id.int:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        entries = list(request.query_params.multi_items())
        if (len(entries) > 2
                or len({key for key, _ in entries}) != len(entries)
                or any(key not in {"page_size", "cursor"} for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        params = dict(entries)
        raw_size = params.get("page_size", "50")
        if (_PAGE_SIZE.fullmatch(raw_size) is None
                or not 1 <= int(raw_size) <= 100):
            raise ApplicationError("VALIDATION_FAILED")
        try:
            query = ListAITasks(
                _session_cookie(headers), uuid.UUID(request.state.trace_id),
                project_id, int(raw_size),
            )
            if "cursor" in params:
                query = replace(
                    query, before=cursors.decode(params["cursor"], query=query),
                )
            page = await run_in_threadpool(reads.list, query)
            if type(page) is not AITaskPage:
                raise ValueError()
            page.__post_init__()
            if len(page.items) > query.page_size:
                raise ValueError()
            cursor = (cursors.encode(query=query, before=page.next_position)
                      if page.has_more and page.next_position is not None else None)
            data = {
                "items": [_public(item) for item in page.items],
                "next_cursor": cursor,
                "has_more": page.has_more,
            }
        except AITaskReadError as error:
            code = {
                "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
                "VALIDATION_FAILED": "VALIDATION_FAILED",
                "REQUEST_MALFORMED": "REQUEST_MALFORMED",
            }.get(error.code, "SYSTEM_UNAVAILABLE")
            raise ApplicationError(code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id},
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
