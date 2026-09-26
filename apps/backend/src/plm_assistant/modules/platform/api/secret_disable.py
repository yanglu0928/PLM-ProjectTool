"""Opt-in Secret disable HTTP boundary with no request body."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.api.secret_create import _write_error
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.application.secret_access import SecretRef
from plm_assistant.modules.platform.application.secret_write import (
    DisableSecret, SecretWriteError, SecretWriteService,
)


def create_secret_disable_router(*, sessions: SessionService,
                                 writes: SecretWriteService,
                                 origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or writes is None or origins is None:
        raise ValueError("session, Secret write service and origins are required")
    router = APIRouter()

    @router.post("/api/v1/admin/secrets/{secret_id}:disable")
    async def disable_secret(secret_id: uuid.UUID, request: Request) -> JSONResponse:
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
        expected = parse_if_match(headers)
        if secret_id.int == 0:
            raise ApplicationError("VALIDATION_FAILED")
        async for chunk in request.stream():
            if chunk:
                raise ApplicationError("REQUEST_MALFORMED")
        try:
            await run_in_threadpool(writes.disable, DisableSecret(
                token, csrf, SecretRef(secret_id), expected,
                uuid.UUID(request.state.trace_id), key,
            ))
        except SecretWriteError as exc:
            raise _write_error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": {"secret_id": str(secret_id), "state": "DISABLED",
                      "current_version_no": None},
             "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": f'"v{expected + 1}"'},
        )

    return router
