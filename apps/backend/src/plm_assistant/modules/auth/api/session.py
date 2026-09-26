"""Opt-in, read-only current Session HTTP projection."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.auth.application.session_view import SessionViewPort
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, validate_idempotency_key,
)


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


def _csrf_header(headers: tuple[tuple[bytes, bytes], ...]) -> bytes:
    try:
        values = [value.decode("ascii") for name, value in headers if name.lower() == b"x-csrf-token"]
        if len(values) != 1 or _TOKEN.fullmatch(values[0]) is None:
            raise ValueError()
        return bytes.fromhex(values[0])
    except (AttributeError, TypeError, UnicodeDecodeError, ValueError):
        raise ApplicationError("AUTH_CSRF_INVALID") from None


def _session_failure(exc: SessionError) -> ApplicationError:
    if exc.code == "AUTH_ACCESS_DENIED":
        return ApplicationError("AUTH_CSRF_INVALID")
    if exc.code == "SYSTEM_UNAVAILABLE":
        return ApplicationError("SYSTEM_UNAVAILABLE")
    return ApplicationError("AUTH_SESSION_EXPIRED")


def _idempotency_header(headers: tuple[tuple[bytes, bytes], ...]) -> str:
    try:
        values = [value.decode("ascii") for name, value in headers if name.lower() == b"idempotency-key"]
        if len(values) != 1:
            raise ValueError()
        return validate_idempotency_key(values[0])
    except (AttributeError, TypeError, UnicodeDecodeError, ValueError):
        raise ApplicationError("VALIDATION_FAILED") from None


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


def create_session_logout_router(*, sessions: SessionService,
                                 origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or origins is None:
        raise ValueError("session and origins are required")
    router = APIRouter()

    @router.post("/api/v1/auth/logout")
    async def logout_session(request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf, key = (
            _session_cookie(headers), _csrf_header(headers), _idempotency_header(headers),
        )
        async for chunk in request.stream():
            if chunk:
                raise ApplicationError("REQUEST_MALFORMED")
        try:
            revoked = await run_in_threadpool(
                sessions.logout, token=token, csrf_token=csrf,
                idempotency_key=key, trace_id=uuid.UUID(request.state.trace_id),
            )
        except IdempotencyError:
            raise
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if revoked is not True:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        response = JSONResponse(
            {"data": {"revoked": True}, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store"},
        )
        response.delete_cookie(
            "plm_session", path="/", secure=request.headers["origin"].startswith("https://"),
            httponly=True, samesite="lax",
        )
        return response

    return router


def create_session_renew_router(*, sessions: SessionService, views: SessionViewPort,
                                origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or views is None or origins is None:
        raise ValueError("session, identity projection and origins are required")
    router = APIRouter()

    @router.post("/api/v1/auth/session:renew")
    async def renew_session(request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf = _session_cookie(headers), _csrf_header(headers)
        async for chunk in request.stream():
            if chunk:
                raise ApplicationError("REQUEST_MALFORMED")
        try:
            principal = await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True,
            )
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        # Project/identity projection must be available before the old token
        # is retired; otherwise a 503 would strand the browser without either.
        try:
            view = await run_in_threadpool(views.resolve, principal.user_id)
            if view.user_id != principal.user_id:
                raise RuntimeError("identity projection mismatch")
            public = view.public_data()
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        try:
            issued = await run_in_threadpool(
                sessions.renew, token=token, csrf_token=csrf,
                trace_id=uuid.UUID(request.state.trace_id),
            )
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        now = datetime.now(timezone.utc)
        max_age = max(0, min(int((issued.absolute_expires_at - now).total_seconds()),
                             int((issued.idle_expires_at - now).total_seconds())))
        response = JSONResponse({"data": {
            **public,
            "absolute_expires_at": issued.absolute_expires_at.isoformat(),
            "idle_expires_at": issued.idle_expires_at.isoformat(),
            "csrf_token": issued.csrf_token.hex(),
        }, "trace_id": request.state.trace_id}, headers={"Cache-Control": "no-store"})
        response.set_cookie(
            "plm_session", issued.token.hex(), max_age=max_age,
            path="/", secure=request.headers["origin"].startswith("https://"),
            httponly=True, samesite="lax",
        )
        return response

    return router
