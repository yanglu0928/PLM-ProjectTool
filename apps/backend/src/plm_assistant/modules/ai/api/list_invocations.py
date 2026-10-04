"""Opt-in frozen AI_TASK_INVOCATION_LIST minimal HTTP projection."""

from __future__ import annotations

import re
import uuid
from dataclasses import replace
from datetime import timezone
from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.api.invocation_list_cursor import (
    AIInvocationListCursorCodec,
)
from plm_assistant.modules.ai.application.invocation_read import (
    AIInvocationPage,
    AIInvocationReadError,
    AIInvocationView,
    ListAIInvocations,
)
from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError,
    LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.platform.application.errors import ApplicationError


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)


class AIInvocationListPort(Protocol):
    def list(self, query: ListAIInvocations) -> AIInvocationPage: ...


def _public(value: AIInvocationView) -> dict[str, object]:
    if type(value) is not AIInvocationView:
        raise ValueError("invalid AI Invocation projection")
    value.__post_init__()
    stamp = lambda item: (None if item is None else item.astimezone(timezone.utc)
                          .isoformat().replace("+00:00", "Z"))
    context = None
    if value.context is not None:
        context = {
            "content_plan_id": str(value.context.content_plan_id),
            "content_plan_version": value.context.content_plan_version,
            "context_policy_ref": value.context.context_policy_ref,
            "mode": value.context.mode,
            "retrieval_run_id": (None if value.context.retrieval_run_id is None
                                 else str(value.context.retrieval_run_id)),
            "context_bundle_id": (None if value.context.context_bundle_id is None
                                  else str(value.context.context_bundle_id)),
        }
    return {
        "ai_invocation_id": str(value.ai_invocation_id),
        "ai_task_id": str(value.ai_task_id),
        "attempt_no": value.attempt_no,
        "provider": {
            "ai_provider_id": str(value.ai_provider_id),
            "provider_config_version_id": str(value.provider_config_version_id),
        },
        "model": {
            "ai_model_id": str(value.ai_model_id),
            "revision": value.model_revision,
        },
        "prompt_version_ref": {
            "prompt_template_id": str(value.prompt_template_id),
            "version_no": value.prompt_version_no,
        },
        "output_schema": {
            "ref": value.output_schema_ref,
            "version": value.schema_version,
        },
        "context": context,
        "invocation_state": value.invocation_state,
        "schema_validation_state": value.schema_validation_state,
        "usage": {
            "input_tokens": value.usage_input_tokens,
            "output_tokens": value.usage_output_tokens,
        },
        "latency_ms": value.latency_ms,
        "error_code": value.error_code,
        "retryable": value.retryable,
        "created_at": stamp(value.created_at),
        "started_at": stamp(value.started_at),
        "completed_at": stamp(value.completed_at),
    }


def create_ai_invocation_list_router(*, reads: AIInvocationListPort,
                                     origins: LoginOriginPolicy,
                                     cursors: AIInvocationListCursorCodec) -> APIRouter:
    if any(value is None for value in (reads, origins, cursors)):
        raise ValueError("AI Invocation list dependencies required")
    router = APIRouter()

    @router.get(
        "/api/v1/projects/{project_id}/ai-tasks/{ai_task_id}/invocations"
    )
    async def list_invocations(project_id: uuid.UUID, ai_task_id: uuid.UUID,
                               request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        if not project_id.int or not ai_task_id.int:
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
            query = ListAIInvocations(
                _session_cookie(headers), uuid.UUID(request.state.trace_id),
                project_id, ai_task_id, int(raw_size),
            )
            if "cursor" in params:
                query = replace(
                    query, before=cursors.decode(params["cursor"], query=query),
                )
            page = await run_in_threadpool(reads.list, query)
            if type(page) is not AIInvocationPage:
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
        except AIInvocationReadError as error:
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
