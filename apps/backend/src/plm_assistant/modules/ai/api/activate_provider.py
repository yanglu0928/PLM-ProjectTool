"""Opt-in, request-body-free Provider activation HTTP boundary."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.application.activate_provider import (
    AIProviderActivationError, AIProviderActivationService, ActivateAIProvider,
    ActivatedAIProvider,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError


def _error(exc: AIProviderActivationError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "AI_PROVIDER_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "AI_PROVIDER_STATE_CONFLICT": "CONFLICT_STATE",
        "AI_PROVIDER_TEST_REQUIRED": "CONFLICT_STATE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "AI_PROVIDER_UNAVAILABLE")
    return ApplicationError(code)


def create_ai_provider_activate_router(*, sessions: SessionService,
                                       providers: AIProviderActivationService,
                                       origins: LoginOriginPolicy) -> APIRouter:
    if any(value is None for value in (sessions, providers, origins)):
        raise ValueError("session, Provider activation service and origins are required")
    router = APIRouter()

    @router.post("/api/v1/admin/ai/providers/{provider_id}:activate")
    async def activate_ai_provider(provider_id: uuid.UUID, request: Request) -> JSONResponse:
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
        if not provider_id.int:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        async for chunk in request.stream():
            if chunk:
                raise ApplicationError("REQUEST_MALFORMED")
        try:
            result = await run_in_threadpool(providers.activate, ActivateAIProvider(
                token, csrf, uuid.UUID(request.state.trace_id), provider_id, expected, key,
            ))
        except AIProviderActivationError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not ActivatedAIProvider or result.provider_id != provider_id
                or result.expected_lock_version != expected or result.state != "ACTIVE"):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        try:
            result.__post_init__()
        except AIProviderActivationError:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": {"provider_id": str(result.provider_id), "state": result.state,
                      "etag": result.etag}, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": result.etag},
        )

    return router
