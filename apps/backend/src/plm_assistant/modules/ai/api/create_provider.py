"""Opt-in, credential-free Provider creation HTTP boundary."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.api.provider_metadata import _public
from plm_assistant.modules.ai.application.create_provider import (
    AIProviderCreateError, AIProviderCreateService, CreateAIProvider,
)
from plm_assistant.modules.ai.application.provider_metadata import AIProviderMetadataView
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability, ProviderKind
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError


MAX_PROVIDER_CREATE_BODY = 8192
_FIELDS = frozenset({
    "kind", "display_name", "endpoint_policy_ref", "secret_ref",
    "data_region", "egress_class", "capabilities",
})


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("nonstandard JSON constant")


async def _read_json(request: Request, headers: tuple[tuple[bytes, bytes], ...]) -> object:
    content_types = [value for name, value in headers if name.lower() == b"content-type"]
    if (len(content_types) != 1 or content_types[0].strip().lower() not in (
            b"application/json", b"application/json; charset=utf-8")):
        raise ApplicationError("REQUEST_MALFORMED")
    raw = bytearray()
    try:
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_PROVIDER_CREATE_BODY:
                raise ApplicationError("REQUEST_MALFORMED")
            raw.extend(chunk)
        try:
            return json.loads(raw.decode("utf-8", errors="strict"),
                              object_pairs_hook=_unique_pairs,
                              parse_constant=_reject_constant)
        except (UnicodeDecodeError, ValueError, TypeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
    finally:
        raw[:] = b"\x00" * len(raw)


def _canonical_uuid(value: object) -> uuid.UUID:
    if type(value) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ApplicationError("VALIDATION_FAILED") from None
    if parsed.int == 0 or str(parsed) != value:
        raise ApplicationError("VALIDATION_FAILED")
    return parsed


def _command(body: object, *, token: bytes, csrf: bytes,
             trace_id: uuid.UUID, key: str) -> CreateAIProvider:
    if type(body) is not dict or set(body) != _FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    if (any(type(body[name]) is not str for name in _FIELDS - {"capabilities"})
            or type(body["capabilities"]) is not list
            or not 1 <= len(body["capabilities"]) <= len(ProviderCapability)
            or any(type(item) is not str for item in body["capabilities"])
            or len(set(body["capabilities"])) != len(body["capabilities"])):
        raise ApplicationError("VALIDATION_FAILED")
    try:
        kind = ProviderKind(body["kind"])
        capabilities = frozenset(ProviderCapability(item) for item in body["capabilities"])
    except ValueError:
        raise ApplicationError("VALIDATION_FAILED") from None
    return CreateAIProvider(
        token, csrf, trace_id, kind, body["display_name"],
        body["endpoint_policy_ref"], _canonical_uuid(body["secret_ref"]),
        body["data_region"], body["egress_class"], capabilities, key,
    )


def _error(exc: AIProviderCreateError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "AI_PROVIDER_SECRET_UNAVAILABLE": "AI_PROVIDER_UNAVAILABLE",
    }.get(exc.code, "AI_PROVIDER_UNAVAILABLE")
    return ApplicationError(code)


def create_ai_provider_create_router(*, sessions: SessionService,
                                     providers: AIProviderCreateService,
                                     origins: LoginOriginPolicy) -> APIRouter:
    if any(item is None for item in (sessions, providers, origins)):
        raise ValueError("session, Provider create service and origins are required")
    router = APIRouter()

    @router.post("/api/v1/admin/ai/providers")
    async def create_ai_provider(request: Request) -> JSONResponse:
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
            view = await run_in_threadpool(providers.create_view, command)
        except AIProviderCreateError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not AIProviderMetadataView or view.state != "CONFIGURED" or view.etag != '"v0"':
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = _public(view)
        path = f"/api/v1/admin/ai/providers/{view.provider_id}"
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id}, status_code=201,
            headers={"Cache-Control": "no-store", "ETag": view.etag, "Location": path},
        )

    return router
