"""Opt-in write-only Secret creation HTTP boundary; no value in any response."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.application.secret_access import SecretConsumer, SecretPurpose, SecretRef
from plm_assistant.modules.platform.application.secret_write import (
    CreateSecret, SecretWriteError, SecretWriteService,
)


MAX_SECRET_CREATE_BODY = 70_000


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("nonstandard JSON constant")


def _write_error(exc: SecretWriteError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "PLATFORM_SECRET_PURPOSE_INVALID": "PLATFORM_SECRET_PURPOSE_INVALID",
        "PLATFORM_SECRET_UNAVAILABLE": "PLATFORM_SECRET_UNAVAILABLE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def _require_json_content_type(headers: tuple[tuple[bytes, bytes], ...]) -> None:
    content_types = [value for name, value in headers if name.lower() == b"content-type"]
    if (len(content_types) != 1
            or content_types[0].split(b";", 1)[0].strip().lower() != b"application/json"):
        raise ApplicationError("REQUEST_MALFORMED")


async def _read_secret_json(request: Request) -> object:
    raw = bytearray()
    try:
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_SECRET_CREATE_BODY:
                raise ApplicationError("REQUEST_MALFORMED")
            raw.extend(chunk)
        try:
            return json.loads(raw.decode("utf-8", errors="strict"),
                              object_pairs_hook=_unique_pairs,
                              parse_constant=_reject_constant)
        except (ValueError, UnicodeDecodeError, TypeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
    finally:
        raw[:] = b"\x00" * len(raw)


def create_secret_create_router(*, sessions: SessionService,
                                writes: SecretWriteService,
                                origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or writes is None or origins is None:
        raise ValueError("session, Secret write service and origins are required")
    router = APIRouter()

    @router.post("/api/v1/admin/secrets")
    async def create_secret(request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token = _session_cookie(headers)
        csrf = _csrf_header(headers)
        key = _idempotency_header(headers)
        try:
            await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True,
            )
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        _require_json_content_type(headers)
        body = await _read_secret_json(request)
        if (type(body) is not dict
                or set(body) != {"purpose", "allowed_consumer", "secret_value"}
                or type(body["purpose"]) is not str
                or type(body["allowed_consumer"]) is not str
                or type(body["secret_value"]) is not str):
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            purpose = SecretPurpose(body["purpose"])
            consumer = SecretConsumer(body["allowed_consumer"])
        except ValueError:
            raise ApplicationError("PLATFORM_SECRET_PURPOSE_INVALID") from None
        try:
            value = bytearray(body["secret_value"].encode("utf-8", errors="strict"))
        except UnicodeEncodeError:
            raise ApplicationError("VALIDATION_FAILED") from None
        try:
            if not 1 <= len(value) <= 65_520:
                raise ApplicationError("VALIDATION_FAILED")
            ref = await run_in_threadpool(writes.create, CreateSecret(
                token, csrf, purpose, consumer, value,
                uuid.UUID(request.state.trace_id), key,
            ))
        except SecretWriteError as exc:
            raise _write_error(exc) from None
        except ApplicationError:
            raise
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        finally:
            value[:] = b"\x00" * len(value)
        if type(ref) is not SecretRef:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        path = f"/api/v1/admin/secrets/{ref.secret_id}"
        return JSONResponse(
            {"data": {"secret_id": str(ref.secret_id)},
             "trace_id": request.state.trace_id},
            status_code=201,
            headers={"Cache-Control": "no-store", "ETag": '"v1"', "Location": path},
        )

    return router
