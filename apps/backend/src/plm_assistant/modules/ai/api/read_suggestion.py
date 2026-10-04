"""Opt-in frozen AI_TASK_SUGGESTION_GET transport projection."""

from __future__ import annotations

import uuid
from datetime import timezone
from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.application.suggestion_read import (
    AISuggestionReadError,
    AISuggestionView,
    GetAISuggestion,
)
from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError,
    LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.platform.application.errors import ApplicationError


class AISuggestionReadPort(Protocol):
    def get(self, query: GetAISuggestion) -> AISuggestionView: ...


def _public(value: AISuggestionView) -> dict[str, object]:
    if type(value) is not AISuggestionView:
        raise ValueError("invalid AI Suggestion projection")
    value.__post_init__()
    record = value.record
    stamp = record.created_at.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z",
    )
    locations = []
    for item in value.locations:
        locations.append({
            "source_ordinal": item.source_ordinal,
            "document_id": str(item.document_id),
            "document_version_id": str(item.document_version_id),
            "precision": item.precision,
            "content_url": item.content_url,
            "locations": list(item.locations),
        })
    return {
        "ai_task_id": str(record.ai_task_id),
        "ai_invocation_id": str(record.ai_invocation_id),
        "suggestion_payload_id": str(record.suggestion_payload_id),
        "project_id": str(record.project_id),
        "suggestion_state": record.suggestion_state,
        "fact_status": record.fact_status,
        "quality_flags": list(record.quality_flags),
        "input_versions": [{
            "resource_type": item.resource_type,
            "resource_id": str(item.resource_id),
            "version_id": str(item.version_id),
        } for item in record.input_versions],
        "provider": {
            "ai_provider_id": str(record.ai_provider_id),
            "provider_config_version_id": str(record.provider_config_version_id),
        },
        "model": {
            "ai_model_id": str(record.ai_model_id),
            "revision": record.model_revision,
        },
        "prompt_version_ref": {
            "prompt_template_id": str(record.prompt_template_id),
            "version_no": record.prompt_version_no,
        },
        "output_schema": {
            "ref": record.output_schema_ref,
            "version": record.schema_version,
        },
        "context": {
            "content_plan_id": str(record.context.content_plan_id),
            "content_plan_version": record.context.content_plan_version,
            "context_policy_ref": record.context.context_policy_ref,
            "mode": record.context.mode,
            "retrieval_run_id": (
                None if record.context.retrieval_run_id is None
                else str(record.context.retrieval_run_id)
            ),
            "context_bundle_id": (
                None if record.context.context_bundle_id is None
                else str(record.context.context_bundle_id)
            ),
        },
        "payload": record.canonical_payload,
        "source_locations": locations,
        "created_at": stamp,
        "etag": f'"v{record.task_lock_version}"',
    }


def create_ai_suggestion_read_router(*, reads: AISuggestionReadPort,
                                     origins: LoginOriginPolicy) -> APIRouter:
    if any(value is None for value in (reads, origins)):
        raise ValueError("AI Suggestion reads and origins required")
    router = APIRouter()

    @router.get(
        "/api/v1/projects/{project_id}/ai-tasks/{ai_task_id}/suggestion"
    )
    async def get_suggestion(project_id: uuid.UUID, ai_task_id: uuid.UUID,
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
            value = await run_in_threadpool(reads.get, GetAISuggestion(
                _session_cookie(headers), uuid.UUID(request.state.trace_id),
                project_id, ai_task_id,
            ))
            data = _public(value)
        except AISuggestionReadError as error:
            code = {
                "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
                "VALIDATION_FAILED": "VALIDATION_FAILED",
            }.get(error.code, "SYSTEM_UNAVAILABLE")
            raise ApplicationError(code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id},
            headers={
                "ETag": str(data["etag"]),
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router
