"""Opt-in login HTTP boundary; production dependencies are wired separately."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.application.login_service import (
    LoginAttempt, LoginError, LoginService,
)
from plm_assistant.modules.auth.application.session_view import SessionViewPort
from plm_assistant.modules.platform.application.errors import ApplicationError


MAX_LOGIN_BODY = 4096


def create_login_router(*, login: LoginService, origins: LoginOriginPolicy,
                        views: SessionViewPort) -> APIRouter:
    if login is None or origins is None or views is None:
        raise ValueError("login, origins and identity projection are required")
    router = APIRouter()

    @router.post("/api/v1/auth/login")
    async def authenticate(request: Request) -> JSONResponse:
        try:
            origins.require_trusted(request.scope.get("headers", ()))
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise ApplicationError("REQUEST_MALFORMED")
        chunks: list[bytes] = []
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > MAX_LOGIN_BODY:
                raise ApplicationError("REQUEST_MALFORMED")
            chunks.append(chunk)
        try:
            body = json.loads(b"".join(chunks))
        except (ValueError, UnicodeDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
        if (type(body) is not dict or set(body) != {"username", "password"}
                or type(body["username"]) is not str
                or type(body["password"]) is not str):
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            password = bytearray(body["password"].encode("utf-8"))
        except UnicodeEncodeError:
            raise ApplicationError("AUTH_INVALID_CREDENTIALS") from None
        client = request.client
        if client is None or not client.host:
            password[:] = b"\x00" * len(password)
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        try:
            issued = await run_in_threadpool(login.login, LoginAttempt(
                username=body["username"], password=password,
                client_ip=client.host, trace_id=uuid.UUID(request.state.trace_id),
            ))
        except LoginError as exc:
            raise ApplicationError(exc.code) from None
        finally:
            password[:] = b"\x00" * len(password)
        try:
            view = await run_in_threadpool(views.resolve, issued.user_id)
            if view.user_id != issued.user_id:
                raise RuntimeError("identity projection mismatch")
            public = view.public_data()
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
        }, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store"})
        response.set_cookie("plm_session", issued.token.hex(), max_age=max_age,
                            path="/", secure=request.headers["origin"].startswith("https://"), httponly=True,
                            samesite="lax")
        return response

    return router
