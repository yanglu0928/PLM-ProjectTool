"""Opt-in PromptTemplate retirement; production trust remains a separate gate."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.api.create_prompt_version import _read_json
from plm_assistant.modules.ai.application.retire_prompt_template import (
    PromptRetireError, PromptTemplateRetireService, RetirePromptTemplate,
    RetiredPromptTemplate,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError


def _error(exc: PromptRetireError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "AI_PROMPT_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "AI_PROMPT_STATE_CONFLICT": "CONFLICT_STATE",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def create_ai_prompt_retire_router(*, sessions: SessionService,
                                   retirements: PromptTemplateRetireService,
                                   origins: LoginOriginPolicy) -> APIRouter:
    if any(value is None for value in (sessions, retirements, origins)):
        raise ValueError("session, Prompt retirement service and origins are required")
    router = APIRouter()

    @router.post("/api/v1/admin/ai/prompt-templates/{prompt_template_id}:retire")
    async def retire_prompt_template(prompt_template_id: uuid.UUID,
                                     request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf, key = (
            _session_cookie(headers), _csrf_header(headers), _idempotency_header(headers),
        )
        try:
            await run_in_threadpool(sessions.validate, token, csrf_token=csrf,
                                    require_csrf=True)
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        expected = parse_if_match(headers)
        if prompt_template_id.int == 0:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        body = await _read_json(request, headers)
        if type(body) is not dict or body:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            result = await run_in_threadpool(retirements.retire, RetirePromptTemplate(
                token, csrf, uuid.UUID(request.state.trace_id), prompt_template_id,
                expected, key,
            ))
        except PromptRetireError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not RetiredPromptTemplate
                or result.prompt_template_id != prompt_template_id
                or result.expected_lock_version != expected):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        try:
            result.__post_init__()
        except PromptRetireError:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": {"prompt_template_id": str(result.prompt_template_id),
                      "state": result.state, "etag": result.etag},
             "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": result.etag},
        )

    return router
