"""Opt-in AIModel registration HTTP; no model activation or outbound call."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.api.create_provider import _canonical_uuid, _read_json
from plm_assistant.modules.ai.api.model_metadata import _public
from plm_assistant.modules.ai.application.create_model import (
    AIModelCreateError, AIModelCreateService, CreateAIModel,
)
from plm_assistant.modules.ai.application.model_metadata import AIModelMetadataView
from plm_assistant.modules.ai.domain.model_definition import AIModelKind
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError


_FIELDS = frozenset({"provider_id", "provider_model_key", "kind", "revision",
                     "embedding_dimension", "capabilities", "quality_profile_refs"})
_CAPABILITIES = frozenset({"structured_output", "context_window_tokens"})


def _command(body: object, *, token: bytes, csrf: bytes,
             trace_id: uuid.UUID, key: str) -> CreateAIModel:
    if type(body) is not dict or set(body) != _FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    capabilities = body["capabilities"]
    if type(capabilities) is not dict or set(capabilities) != _CAPABILITIES:
        raise ApplicationError("REQUEST_MALFORMED")
    if (type(body["provider_model_key"]) is not str or type(body["revision"]) is not str
            or type(body["quality_profile_refs"]) is not list
            or any(type(item) is not str for item in body["quality_profile_refs"])
            or type(capabilities["structured_output"]) is not bool
            or capabilities["context_window_tokens"] is not None
            and type(capabilities["context_window_tokens"]) is not int
            or body["embedding_dimension"] is not None
            and type(body["embedding_dimension"]) is not int):
        raise ApplicationError("VALIDATION_FAILED")
    try:
        kind = AIModelKind(body["kind"])
    except (ValueError, TypeError):
        raise ApplicationError("VALIDATION_FAILED") from None
    return CreateAIModel(
        token, csrf, trace_id, _canonical_uuid(body["provider_id"]),
        body["provider_model_key"], kind, body["revision"], body["embedding_dimension"],
        capabilities["structured_output"], capabilities["context_window_tokens"],
        tuple(body["quality_profile_refs"]), key,
    )


def _error(exc: AIModelCreateError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "AI_MODEL_ALREADY_EXISTS": "CONFLICT_DUPLICATE",
        "AI_MODEL_QUALITY_UNVERIFIED": "VALIDATION_FAILED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def create_ai_model_create_router(*, sessions: SessionService,
                                  models: AIModelCreateService,
                                  origins: LoginOriginPolicy) -> APIRouter:
    if any(item is None for item in (sessions, models, origins)):
        raise ValueError("session, Model create service and origins are required")
    router = APIRouter()

    @router.post("/api/v1/admin/ai/models")
    async def create_ai_model(request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token = _session_cookie(headers)
        csrf = _csrf_header(headers)
        key = _idempotency_header(headers)
        try:
            await run_in_threadpool(sessions.validate, token, csrf_token=csrf, require_csrf=True)
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        body = await _read_json(request, headers)
        command = _command(body, token=token, csrf=csrf,
                           trace_id=uuid.UUID(request.state.trace_id), key=key)
        try:
            view = await run_in_threadpool(models.create_view, command)
        except AIModelCreateError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not AIModelMetadataView or view.state != "SUSPENDED"
                or view.etag != '"v0"' or view.quality_profile_refs):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        path = f"/api/v1/admin/ai/models/{view.model_id}"
        return JSONResponse(
            {"data": _public(view), "trace_id": request.state.trace_id}, status_code=201,
            headers={"Cache-Control": "no-store", "ETag": view.etag, "Location": path},
        )

    return router
