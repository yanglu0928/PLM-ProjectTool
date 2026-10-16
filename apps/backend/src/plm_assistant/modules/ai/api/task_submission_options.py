"""Safe project AI Task submission options; no endpoints, prompts or secrets."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.application.task_submission_options import (
    AITaskSubmissionOptionsError, AITaskSubmissionOptionsService,
    GetAITaskSubmissionOptions,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.platform.application.errors import ApplicationError


def create_ai_task_submission_options_router(
    *, options: AITaskSubmissionOptionsService, origins: LoginOriginPolicy,
) -> APIRouter:
    if any(value is None for value in (options, origins)):
        raise ValueError("AI Task submission options and origins required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/ai-task-options")
    async def get_options(project_id: uuid.UUID, request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        if request.url.query or not project_id.int:
            raise ApplicationError(
                "REQUEST_MALFORMED" if request.url.query else "RESOURCE_NOT_FOUND"
            )
        try:
            view = await run_in_threadpool(options.get, GetAITaskSubmissionOptions(
                _session_cookie(headers), uuid.UUID(request.state.trace_id), project_id,
            ))
        except AITaskSubmissionOptionsError as exc:
            code = {
                "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
                "VALIDATION_FAILED": "VALIDATION_FAILED",
            }.get(exc.code, "SYSTEM_UNAVAILABLE")
            raise ApplicationError(code) from None
        data = {
            "task_policies": [{
                "reference": policy.reference, "policy_version": policy.policy_version,
                "task_type": policy.task_type, "purpose_ref": policy.purpose_ref,
                "output_schema_ref": policy.output_schema_ref,
                "context_policy_ref": policy.context_policy_ref,
                "parameter_fields": [{
                    "name": field.name, "value_type": field.value_type,
                    "required": field.required, "max_length": field.max_length,
                    "minimum": field.minimum, "maximum": field.maximum,
                    "allowed_values": list(field.allowed_values),
                } for field in policy.parameter_fields],
            } for policy in view.task_policies],
            "egress_policies": [{
                "reference": policy.reference,
                "allowed_data_categories": sorted(policy.allowed_data_categories),
                "max_record_count": policy.max_record_count,
                "max_payload_bytes": policy.max_payload_bytes,
                "max_input_tokens": policy.max_input_tokens,
                "max_retry_attempts": policy.max_retry_attempts,
                "risk_codes": list(policy.risk_codes),
                "ttl_seconds": int(policy.ttl.total_seconds()),
            } for policy in view.egress_policies],
            "routes": [{
                "provider_id": str(route.provider_id), "model_id": str(route.model_id),
                "provider_display_name": route.provider_display_name,
                "data_region": route.data_region,
                "provider_model_key": route.provider_model_key,
                "model_revision": route.model_revision,
            } for route in view.routes],
        }
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    return router
