"""Opt-in frozen TraceLink revoke HTTP; default and platform roots stay closed."""

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
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.trace.application.revoke_link import (
    RevokeTraceLink, RevokedTraceLink, TraceRevokeError, TraceRevokeService,
)


def create_trace_revoke_router(*, sessions: SessionService,
                               revokes: TraceRevokeService,
                               origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or revokes is None or origins is None:
        raise ValueError("Trace revoke HTTP dependencies required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/trace-links/{trace_link_id}:revoke",
                 operation_id="TRACE_LINK_REVOKE")
    async def revoke_link(project_id: uuid.UUID, trace_link_id: uuid.UUID,
                          request: Request) -> JSONResponse:
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
        if project_id.int == 0 or trace_link_id.int == 0:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        async for chunk in request.stream():
            if chunk:
                raise ApplicationError("REQUEST_MALFORMED")
        try:
            result = await run_in_threadpool(
                revokes.revoke,
                RevokeTraceLink(
                    token, csrf, uuid.UUID(request.state.trace_id),
                    project_id, trace_link_id, expected,
                ),
                idempotency_key=key,
            )
        except TraceRevokeError as exc:
            code = {
                "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
                "CONFLICT_VERSION": "CONFLICT_VERSION",
                "CONFLICT_STATE": "CONFLICT_STATE",
                "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
                "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
                "VALIDATION_FAILED": "VALIDATION_FAILED",
            }.get(exc.code, "SYSTEM_UNAVAILABLE")
            raise ApplicationError(code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not RevokedTraceLink
                or result.trace_link_id != trace_link_id
                or result.lock_version != 1):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": {"trace_link_id": str(trace_link_id),
                      "link_state": "REVOKED"},
             "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": '"v1"'},
        )

    return router
