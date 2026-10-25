"""Opt-in, request-body-free Provider Test 202 HTTP boundary."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.application.submit_provider_test import (
    AIProviderTestSubmitError, AIProviderTestSubmitService, SubmitAIProviderTest,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.jobs.application.ai_provider_test_enqueue import AIProviderTestJobRef
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError


def _error(exc: AIProviderTestSubmitError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "AI_PROVIDER_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "AI_PROVIDER_STATE_CONFLICT": "CONFLICT_STATE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "AI_PROVIDER_UNAVAILABLE")
    return ApplicationError(code)


def create_ai_provider_test_router(*, sessions: SessionService,
                                   providers: AIProviderTestSubmitService,
                                   origins: LoginOriginPolicy) -> APIRouter:
    if any(value is None for value in (sessions, providers, origins)):
        raise ValueError("session, Provider Test service and origins are required")
    router = APIRouter()

    @router.post("/api/v1/admin/ai/providers/{provider_id}:test")
    async def submit_ai_provider_test(provider_id: uuid.UUID, request: Request) -> JSONResponse:
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
            result = await run_in_threadpool(providers.submit, SubmitAIProviderTest(
                token, csrf, uuid.UUID(request.state.trace_id), provider_id, expected, key,
            ))
        except AIProviderTestSubmitError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(result) is not AIProviderTestJobRef or not result.job_id.int or not result.event_id.int:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": {"job_id": str(result.job_id)}, "trace_id": request.state.trace_id},
            status_code=202,
            headers={"Cache-Control": "no-store",
                     "Location": f"/api/v1/admin/jobs/{result.job_id}"},
        )

    return router
