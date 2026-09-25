"""Opt-in, read-only current Session HTTP projection."""

from __future__ import annotations

import re

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.auth.application.session_view import SessionViewPort
from plm_assistant.modules.platform.application.errors import ApplicationError


_TOKEN = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def _session_cookie(headers: tuple[tuple[bytes, bytes], ...]) -> bytes:
    try:
        cookie_headers = [value.decode("ascii") for name, value in headers if name.lower() == b"cookie"]
        if len(cookie_headers) != 1:
            raise ValueError()
        values = []
        for segment in cookie_headers[0].split(";"):
            name, separator, value = segment.strip().partition("=")
            if name == "plm_session":
                values.append(value if separator else "")
        if len(values) != 1 or _TOKEN.fullmatch(values[0]) is None:
            raise ValueError()
        return bytes.fromhex(values[0])
    except (AttributeError, TypeError, UnicodeDecodeError, ValueError):
        raise ApplicationError("AUTH_SESSION_EXPIRED") from None


def create_session_read_router(*, sessions: SessionService, views: SessionViewPort,
                               origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or views is None or origins is None:
        raise ValueError("session, identity projection and origins are required")
    router = APIRouter()

    @router.get("/api/v1/auth/session")
    async def current_session(request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token = _session_cookie(headers)
        try:
            principal = await run_in_threadpool(sessions.validate, token)
        except SessionError:
            raise ApplicationError("AUTH_SESSION_EXPIRED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        try:
            view = await run_in_threadpool(views.resolve, principal.user_id)
            if view.user_id != principal.user_id:
                raise RuntimeError("identity projection mismatch")
            public = view.public_data()
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({"data": {
            **public,
            "absolute_expires_at": principal.absolute_expires_at.isoformat(),
            "idle_expires_at": principal.idle_expires_at.isoformat(),
        }, "trace_id": request.state.trace_id}, headers={"Cache-Control": "no-store"})

    return router
