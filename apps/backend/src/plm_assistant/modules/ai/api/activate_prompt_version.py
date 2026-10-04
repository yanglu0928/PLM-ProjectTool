"""Opt-in PromptVersion activation; production requires trusted admission."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.api.create_prompt_version import _read_json
from plm_assistant.modules.ai.application.activate_prompt_version import (
    ActivatePromptVersion, ActivatedPromptVersion, PromptActivationError,
    PromptVersionActivationService,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError


def _error(exc: PromptActivationError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "AI_PROMPT_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "AI_PROMPT_VERSION_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "AI_PROMPT_STATE_CONFLICT": "CONFLICT_STATE",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "AI_PROMPT_CONTENT_UNAPPROVED": "VALIDATION_FAILED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def create_ai_prompt_activation_router(*, sessions: SessionService,
                                       activations: PromptVersionActivationService,
                                       origins: LoginOriginPolicy) -> APIRouter:
    if any(value is None for value in (sessions, activations, origins)):
        raise ValueError("session, Prompt activation service and origins are required")
    router = APIRouter()

    @router.post("/api/v1/admin/ai/prompt-templates/{prompt_template_id}/versions/{version_no}:activate")
    async def activate_prompt_version(prompt_template_id: uuid.UUID, version_no: int,
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
        if prompt_template_id.int == 0 or not 1 <= version_no <= 9223372036854775807:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        body = await _read_json(request, headers)
        if type(body) is not dict or body:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            result = await run_in_threadpool(activations.activate, ActivatePromptVersion(
                token, csrf, uuid.UUID(request.state.trace_id), prompt_template_id,
                version_no, expected, key,
            ))
        except PromptActivationError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not ActivatedPromptVersion
                or result.prompt_template_id != prompt_template_id
                or result.version_no != version_no
                or result.expected_lock_version != expected):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        try:
            result.__post_init__()
        except PromptActivationError:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": {"prompt_template_id": str(result.prompt_template_id),
                      "version_no": result.version_no, "state": result.state,
                      "etag": result.etag}, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": result.etag},
        )

    return router
