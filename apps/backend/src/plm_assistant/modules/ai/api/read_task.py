"""Frozen project AI Task GET with minimized, no-store metadata."""

from __future__ import annotations

import uuid
from datetime import timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.application.task_read import (
    AITaskReadError, AITaskReadService, AITaskView, GetAITask,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.platform.application.errors import ApplicationError


def _public(value: AITaskView) -> dict[str, object]:
    if type(value) is not AITaskView:
        raise ValueError("invalid AI Task projection")
    value.__post_init__()
    stamp = lambda item: (None if item is None else item.astimezone(timezone.utc)
                          .isoformat().replace("+00:00", "Z"))
    return {
        "ai_task_id": str(value.ai_task_id), "project_id": str(value.project_id),
        "task_type": value.task_type, "requested_by": str(value.requested_by),
        "input_refs": [{"resource_type": item.resource_type,
                        "resource_id": str(item.resource_id),
                        "version_id": str(item.version_id)} for item in value.input_refs],
        "prompt_policy_ref": value.prompt_policy_ref,
        "prompt_policy_version": value.prompt_policy_version,
        "prompt_version_ref": None if value.prompt_template_ref is None else {
            "prompt_template_id": str(value.prompt_template_ref),
            "version_no": value.prompt_version_no,
        },
        "output_schema_ref": value.output_schema_ref,
        "context_policy_ref": value.context_policy_ref,
        "egress_authorization_ref": (None if value.egress_authorization_ref is None
                                     else str(value.egress_authorization_ref)),
        "job_id": None if value.job_ref is None else str(value.job_ref),
        "current_invocation_id": (None if value.current_invocation_ref is None
                                  else str(value.current_invocation_ref)),
        "task_state": value.task_state, "suggestion_state": value.suggestion_state,
        "trace_id": str(value.trace_id), "error_code": value.error_code,
        "retryable": value.retryable, "requested_at": stamp(value.requested_at),
        "started_at": stamp(value.started_at), "completed_at": stamp(value.completed_at),
        "etag": f'"v{value.lock_version}"',
    }


def create_ai_task_read_router(*, reads: AITaskReadService,
                               origins: LoginOriginPolicy) -> APIRouter:
    if any(value is None for value in (reads, origins)):
        raise ValueError("AI Task reads and origins required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/ai-tasks/{ai_task_id}")
    async def get_task(project_id: uuid.UUID, ai_task_id: uuid.UUID,
                       request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        if request.url.query or not project_id.int or not ai_task_id.int:
            raise ApplicationError(
                "REQUEST_MALFORMED" if request.url.query else "RESOURCE_NOT_FOUND"
            )
        try:
            value = await run_in_threadpool(reads.get, GetAITask(
                _session_cookie(headers), uuid.UUID(request.state.trace_id),
                project_id, ai_task_id,
            ))
            data = _public(value)
        except AITaskReadError as exc:
            code = {
                "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
                "VALIDATION_FAILED": "VALIDATION_FAILED",
            }.get(exc.code, "SYSTEM_UNAVAILABLE")
            raise ApplicationError(code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id},
            headers={"ETag": str(data["etag"]), "Cache-Control": "no-store",
                     "X-Content-Type-Options": "nosniff"},
        )

    return router
