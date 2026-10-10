"""Opt-in controlled partial Provider configuration PATCH boundary."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.api.create_provider import _canonical_uuid, _read_json
from plm_assistant.modules.ai.application.append_provider_config import (
    AIProviderAppendError, AIProviderAppendService, AppendedAIProviderConfigResult,
    PatchAIProviderConfig,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _csrf_header, _session_cookie, _session_failure
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.application.idempotency import IdempotencyError, validate_idempotency_key


_FIELDS = frozenset({
    "display_name", "endpoint_policy_ref", "secret_ref",
    "data_region", "egress_class", "capabilities",
})


def _optional_key(headers: tuple[tuple[bytes, bytes], ...]) -> str:
    values = [value for name, value in headers if name.lower() == b"idempotency-key"]
    if not values:
        return str(uuid.uuid4())
    if len(values) != 1:
        raise ApplicationError("REQUEST_MALFORMED")
    try:
        return validate_idempotency_key(values[0].decode("ascii", errors="strict"))
    except (UnicodeDecodeError, IdempotencyError):
        raise ApplicationError("VALIDATION_FAILED") from None


def _changes(body: object) -> dict[str, object]:
    if type(body) is not dict or not body or set(body) - _FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    changes: dict[str, object] = {}
    for key, value in body.items():
        if key == "secret_ref":
            changes[key] = _canonical_uuid(value)
        elif key == "capabilities":
            if (type(value) is not list or not 1 <= len(value) <= len(ProviderCapability)
                    or any(type(item) is not str for item in value)
                    or len(set(value)) != len(value)):
                raise ApplicationError("VALIDATION_FAILED")
            try:
                changes[key] = frozenset(ProviderCapability(item) for item in value)
            except ValueError:
                raise ApplicationError("VALIDATION_FAILED") from None
        elif type(value) is str:
            changes[key] = value
        else:
            raise ApplicationError("VALIDATION_FAILED")
    return changes


def _error(exc: AIProviderAppendError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "AI_PROVIDER_STATE_CONFLICT": "CONFLICT_STATE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "AI_PROVIDER_UNAVAILABLE")
    return ApplicationError(code)


def create_ai_provider_patch_router(*, sessions: SessionService,
                                    providers: AIProviderAppendService,
                                    origins: LoginOriginPolicy) -> APIRouter:
    if any(item is None for item in (sessions, providers, origins)):
        raise ValueError("session, Provider append service and origins are required")
    router = APIRouter()

    @router.patch("/api/v1/admin/ai/providers/{provider_id}")
    async def patch_ai_provider(provider_id: uuid.UUID, request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token = _session_cookie(headers)
        csrf = _csrf_header(headers)
        try:
            await run_in_threadpool(sessions.validate, token, csrf_token=csrf, require_csrf=True)
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        expected = parse_if_match(headers)
        if provider_id.int == 0:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        key = _optional_key(headers)
        changes = _changes(await _read_json(request, headers))
        try:
            result = await run_in_threadpool(providers.patch_result, PatchAIProviderConfig(
                token, csrf, uuid.UUID(request.state.trace_id), provider_id,
                expected, changes, key,
            ))
        except AIProviderAppendError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not AppendedAIProviderConfigResult
                or result.provider_id != provider_id or result.config_version < 2
                or result.lock_version != expected + 1
                or result.etag != f'"v{expected + 1}"'):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": {"provider_id": str(provider_id),
                      "config_version": result.config_version,
                      "etag": result.etag},
             "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": result.etag},
        )

    return router
