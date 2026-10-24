"""Opt-in safe AIModel :set-state HTTP, with AVAILABLE deliberately closed."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.api.create_provider import _read_json
from plm_assistant.modules.ai.application.change_model_state import (
    AIModelStateError, AIModelStateResult, AIModelStateService, ChangeAIModelState,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError


def _error(exc: AIModelStateError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def create_ai_model_state_router(*, sessions: SessionService,
                                 models: AIModelStateService,
                                 origins: LoginOriginPolicy) -> APIRouter:
    if any(value is None for value in (sessions, models, origins)):
        raise ValueError("session, Model state service and origins are required")
    router = APIRouter()

    @router.post("/api/v1/admin/ai/models/{model_id}:set-state")
    async def set_ai_model_state(model_id: uuid.UUID, request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf, key = (
            _session_cookie(headers), _csrf_header(headers), _idempotency_header(headers),
        )
        try:
            await run_in_threadpool(sessions.validate, token, csrf_token=csrf, require_csrf=True)
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        expected = parse_if_match(headers)
        if model_id.int == 0:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != {"state"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["state"]) is not str or body["state"] not in {"SUSPENDED", "RETIRED"}:
            raise ApplicationError("VALIDATION_FAILED")
        operation = {"SUSPENDED": "SUSPEND", "RETIRED": "RETIRE"}[body["state"]]
        try:
            result = await run_in_threadpool(models.change, ChangeAIModelState(
                token, csrf, uuid.UUID(request.state.trace_id), model_id, expected,
                operation, key,
            ))
        except AIModelStateError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not AIModelStateResult or result.model_id != model_id
                or result.expected_lock_version != expected or result.operation != operation
                or result.state != body["state"]):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        try:
            result.__post_init__()
        except AIModelStateError:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": {"model_id": str(result.model_id), "state": result.state,
                      "etag": result.etag}, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": result.etag},
        )

    return router
